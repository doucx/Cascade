import asyncio
import logging
from typing import Tuple
from cascade.spec.physical.nodes import Token
from cascade.vm.reactor import Reactor
from cascade.vm.compute.service import LocalComputeService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        ingress_queue: "asyncio.Queue[Tuple[str, Token]]",
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.ingress_queue = ingress_queue

    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

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
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and self.ingress_queue.empty()
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
                            continue

                    # 3. Adaptive Throttling
                    if fired_count > 0:
                        await asyncio.sleep(0)
                    else:
                        if not self.ingress_queue.empty():
                            await asyncio.sleep(0)
                        else:
                            await asyncio.sleep(0.001)

                except Exception as e:
                    logger.critical(f"Machine loop crashed: {e}", exc_info=True)
                    # Force shutdown on machine loop crash
                    self.reactor.shutdown_event.set()

            logger.info("Machine shutdown signal received.")

        finally:
            # Shutdown sequence
            self.compute_service.stop()
            service_task.cancel()
            try:
                await service_task
            except asyncio.CancelledError:
                pass
            logger.info("Machine stopped.")
