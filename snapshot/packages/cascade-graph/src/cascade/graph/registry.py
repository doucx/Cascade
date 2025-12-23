from typing import Dict, Callable
from cascade.graph.model import Node


class NodeRegistry:
    """
    A session-level registry that ensures any structurally identical node
    is represented by a single, unique object in memory (interning).
    """

    def __init__(self):
        # Maps a node's shallow structural hash to the Node object
        self._registry: Dict[str, Node] = {}

    def get(self, key: str) -> Node | None:
        """Gets a node by its structural hash key."""
        return self._registry.get(key)

    def get_or_create(
        self, key: str, node_factory: Callable[[], Node]
    ) -> tuple[Node, bool]:
        """
        Gets a node from the registry or creates it using the factory if not found.

        Returns:
            A tuple of (Node, bool) where the boolean is True if the node was newly created.
        """
        existing_node = self.get(key)
        if existing_node:
            return existing_node, False

        new_node = node_factory()
        self._registry[key] = new_node
        return new_node, True
