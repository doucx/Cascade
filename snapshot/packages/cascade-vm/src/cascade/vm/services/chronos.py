import asyncio
import logging
from typing import Tuple

from cascade.spec.physical.nodes import Token
from cascade.vm.services.contracts import DelayRequest

logger = logging.getLogger(__name__)


class ChronosService:
    """
    A service that handles time-based delays asynchronously.
    """

    def __init__(
        self,
        inbound_queue: "asyncio.Queue[DelayRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        wakeup_event: asyncio.Event,
    ):
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.wakeup_event = wakeup_event
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("ChronosService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                asyncio.create_task(self._handle_request(request))
        finally:
            logger.info("ChronosService stopped.")

    def stop(self) -> None:
        self._running = False

    async def _handle_request(self, request: DelayRequest) -> None:
        try:
            await asyncio.sleep(request.delay_seconds)
            await self.outbound_queue.put((request.target_nid, request.token))
            self.wakeup_event.set()
        except asyncio.CancelledError:
            logger.debug("Delay request cancelled.")
        except Exception:
            logger.exception(
                f"ChronosService failed to handle delay request for {request.target_nid}"
            )