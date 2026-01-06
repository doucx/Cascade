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
            while True:
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check for Quiescence
                ingress_empty = self.ingress_queue.empty()
                compute_idle = self.compute_service.is_idle()

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Machine Step: fired={fired_count}, "
                        f"ingress_empty={ingress_empty}, "
                        f"compute_idle={compute_idle} "
                        f"(inbound={self.compute_service.inbound_queue.qsize()}, "
                        f"active={self.compute_service._active_count})"
                    )

                # If the reactor did nothing, and there's no pending I/O...
                if fired_count == 0 and ingress_empty:
                    # ...and the compute service has no active workers...
                    if compute_idle:
                        logger.info("Machine idle. Stopping.")
                        break

                    # If we are just waiting for Compute, yield to the event loop
                    # to give the Service a chance to work.
                    await asyncio.sleep(0.001)
                else:
                    # If we did work, yield briefly to allow I/O ingress processing
                    # but return quickly to sustain high throughput.
                    await asyncio.sleep(0)

        finally:
            # Shutdown sequence
            self.compute_service.stop()
            service_task.cancel()
            try:
                await service_task
            except asyncio.CancelledError:
                pass
            logger.info("Machine stopped.")
