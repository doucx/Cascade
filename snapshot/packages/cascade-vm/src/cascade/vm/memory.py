from typing import Dict
from collections import deque
from cascade.spec.physics import Token, PhysicsDataNode


class MemoryError(Exception):
    """Base class for memory-related errors."""

    pass


class MemoryFullError(MemoryError):
    """Raised when a DataNode exceeds its capacity."""

    pass


class MemoryEmptyError(MemoryError):
    """Raised when attempting to take from an empty DataNode."""

    pass


class VolatileMemory:
    """
    In-memory state manager for PhysicsDataNodes.
    Implements FIFO queues and capacity enforcement.
    """

    def __init__(self):
        # Maps node_id -> deque of Tokens
        self._buffers: Dict[str, deque[Token]] = {}
        # Maps node_id -> capacity
        self._capacities: Dict[str, int] = {}

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        """Adds a token to the specified data node."""
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

    def take(self, node_id: str) -> Token:
        """Consumes and returns the oldest token from the node."""
        if node_id not in self._buffers or not self._buffers[node_id]:
            raise MemoryEmptyError(f"Node '{node_id}' is empty.")

        return self._buffers[node_id].popleft()

    def get_count(self, node_id: str) -> int:
        """Returns the current token count in the node."""
        return len(self._buffers.get(node_id, []))

    def is_excited(self, node_id: str, threshold: int = 1) -> bool:
        """Returns True if the token count meets or exceeds the threshold."""
        return self.get_count(node_id) >= threshold