import asyncio
import random
from typing import Any, Optional
from cascade.interfaces.protocols import Connector


class DirectChannel:
    """
    A high-performance, point-to-point communication primitive.
    Simulates a direct synaptic connection between agents, bypassing the central event bus.
    """

    def __init__(
        self,
        owner_id: str,
        capacity: int = 100,
        sampling_rate: float = 0.001,
        telemetry_connector: Optional[Connector] = None,
    ):
        self.owner_id = owner_id
        # The inbox is a simple asyncio Queue.
        # Unbounded queues are dangerous in prod, but for this proto we want to measure pure throughput.
        # We set a high limit to avoid immediate backpressure during bursts.
        self._inbox = asyncio.Queue(maxsize=capacity)

        # Telemetry Sampling
        self.sampling_rate = sampling_rate
        self.telemetry_connector = telemetry_connector

    async def send(self, payload: Any):
        """
        Directly puts a message into the channel. Zero-copy.
        """
        # 1. Core Logic: Direct Delivery
        # We use await put() to handle backpressure and ensure fair scheduling.
        # This prevents the producer from starving the consumer loop.
        await self._inbox.put(payload)

        # 2. Telemetry Probe (The "Leak")
        # Randomly sample traffic to the global bus for observability.
        if self.telemetry_connector and self.sampling_rate > 0:
            if random.random() < self.sampling_rate:
                # We fire-and-forget the telemetry to minimize impact on the critical path
                asyncio.create_task(
                    self.telemetry_connector.publish(
                        f"debug/sample/{self.owner_id}",
                        {"payload": str(payload), "type": "sample"},
                    )
                )

    async def recv(self) -> Any:
        """
        Waits for a message.
        """
        return await self._inbox.get()

    def qsize(self) -> int:
        return self._inbox.qsize()
