import asyncio
from multiprocessing import Queue
from typing import Any, Dict, Callable, Awaitable
from cascade.interfaces.protocols import Connector, SubscriptionHandle

class IpcUplinkConnector(Connector):
    """
    A specific connector for Worker processes.
    It forwards all published messages to a multiprocessing.Queue.
    It does NOT support subscribing (in this MVP), making it a pure telemetry uplink.
    """

    def __init__(self, uplink_queue: Queue):
        self.uplink_queue = uplink_queue
        self._is_connected = False

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return
        
        # We perform a blocking put (or put_nowait) into the MP queue.
        # Since this runs inside an async loop, we should ideally use run_in_executor,
        # but for high-throughput telemetry, direct put is often acceptable if the queue matches the generation rate.
        # To avoid blocking the event loop on a full queue, we use put_nowait and drop on full (backpressure).
        try:
            self.uplink_queue.put_nowait((topic, payload))
        except Exception:
            # Queue full or closed. In a simulation, dropping frames is better than crashing.
            pass

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        # MVP: Workers do not receive commands from Master yet.
        # Implementation would require a Downlink Queue.
        raise NotImplementedError("IpcUplinkConnector does not support subscriptions yet.")