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
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check Draining State
                # If DRAIN signal was received, we only shutdown when everything is idle.
                if self.reactor.drain_event.is_set():
                    is_reactor_idle = fired_count == 0
                    is_ingress_idle = self.ingress_queue.empty()
                    is_compute_idle = self.compute_service.is_idle()

                    if is_reactor_idle and is_ingress_idle and is_compute_idle:
                        logger.info("System drained successfully. Initiating shutdown.")
                        self.reactor.shutdown_event.set()

                # 3. Adaptive Throttling
                # If the reactor did work, we yield briefly to allow I/O but return ASAP.
                # If it was idle, we sleep longer to save CPU.
                if fired_count > 0:
                    await asyncio.sleep(0)
                else:
                    # Check if there is pending ingress work not yet processed?
                    # Reactor.step() handles ingress, so if fired_count is 0,
                    # it means ingress was empty or didn't trigger any firing.

                    # We can sleep a bit longer to be nice to the CPU,
                    # but check ingress_queue emptiness to be responsive.
                    if not self.ingress_queue.empty():
                        await asyncio.sleep(0)
                    else:
                        # Truly idle loop
                        await asyncio.sleep(0.001)

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
