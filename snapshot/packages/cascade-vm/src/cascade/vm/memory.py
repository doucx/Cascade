from typing import Dict
import asyncio
from collections import deque
from cascade.spec.physics import Token, PhysicsDataNode


class MemoryError(Exception):
    pass


class MemoryFullError(MemoryError):
    pass


class MemoryEmptyError(MemoryError):
    pass


class VolatileMemory:
    def __init__(self):
        # Maps node_id -> deque of Tokens
        self._buffers: Dict[str, deque[Token]] = {}
        # Maps node_id -> capacity
        self._capacities: Dict[str, int] = {}
        self._mutation_event = asyncio.Event()

    async def wait_for_mutation(self) -> None:
        """Wait until a new token is put into memory."""
        await self._mutation_event.wait()
        self._mutation_event.clear()

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        node_id = node.id
        if node_id not in self._buffers:
            self._buffers[node_id] = deque()
            self._capacities[node_id] = node.capacity

        buffer = self._buffers[node_id]
        capacity = self._capacities[node_id]

        if len(buffer) >= capacity:
            raise MemoryFullError(
                f"Node '{node.name}' ({node_id}) with capacity {capacity} is full."
            )

        buffer.append(token)
        self._mutation_event.set()

    def take(self, node_id: str) -> Token:
        if node_id not in self._buffers or not self._buffers[node_id]:
            raise MemoryEmptyError(f"Node '{node_id}' is empty.")

        return self._buffers[node_id].popleft()

    def get_count(self, node_id: str) -> int:
        return len(self._buffers.get(node_id, []))

    def is_excited(self, node_id: str, threshold: int = 1) -> bool:
        return self.get_count(node_id) >= threshold
