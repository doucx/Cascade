import asyncio
import logging
from cascade.vm.protocols import ReactorProtocol, ComputeServiceProtocol
from cascade.vm.services.chronos import ChronosService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: ReactorProtocol,
        compute_service: ComputeServiceProtocol,
        chronos_service: ChronosService,
        wakeup_event: asyncio.Event,
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.chronos_service = chronos_service
        self.wakeup_event = wakeup_event
        # We can get the queue from the reactor, which is the canonical consumer
        self.ingress_queue = reactor.ingress_queue

    async def run(self) -> None:
        logger.info("Machine started.")

        # Start Services
        compute_task = asyncio.create_task(self.compute_service.run())
        chronos_task = asyncio.create_task(self.chronos_service.run())

        try:
            # Run until explicit shutdown signal
            while not self.reactor.shutdown_event.is_set():
                try:
                    # 1. Drive the Physics Kernel (Synchronous Step)
                    fired_count = self.reactor.step()

                    # 2. DRAIN Logic: Check for Quiescence
                    if self.reactor.drain_event.is_set():
                        # System is quiescent if:
                        # - No physics transitions occurred (fired_count == 0)
                        # - No compute tasks are running (active_count == 0)
                        # - No results are pending ingress (ingress_queue empty)
                        is_ingress_pending = (
                            self.ingress_queue and not self.ingress_queue.empty()
                        )
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and not is_ingress_pending
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
                            continue

                    # 3. Adaptive Throttling / Waiting
                    if fired_count > 0 or (
                        self.ingress_queue and not self.ingress_queue.empty()
                    ):
                        # If physics fired or ingress is pending, yield but loop again immediately.
                        await asyncio.sleep(0.001)
                    else:
                        # System is physically idle. Wait for new ingress.
                        try:
                            # Use a timeout to periodically re-check for drain completion
                            await asyncio.wait_for(
                                self.wakeup_event.wait(), timeout=0.1
                            )
                            self.wakeup_event.clear()
                        except asyncio.TimeoutError:
                            pass  # Loop again to check state

                except Exception as e:
                    logger.critical(f"Machine loop crashed: {e}", exc_info=True)
                    # Force shutdown on machine loop crash
                    self.reactor.shutdown_event.set()

            logger.info("Machine shutdown signal received.")

        finally:
            # Shutdown sequence
            self.compute_service.stop()
            self.chronos_service.stop()
            compute_task.cancel()
            chronos_task.cancel()
            try:
                await asyncio.gather(compute_task, chronos_task)
            except asyncio.CancelledError:
                pass
            logger.info("Machine stopped.")
