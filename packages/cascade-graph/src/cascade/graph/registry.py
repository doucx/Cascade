from typing import Dict, Callable
from cascade.graph.model import Node


class NodeRegistry:
    def __init__(self):
        # Maps a node's shallow structural hash to the Node object
        self._registry: Dict[str, Node] = {}

    def get(self, key: str) -> Node | None:
        return self._registry.get(key)

    def get_or_create(
        self, key: str, node_factory: Callable[[], Node]
    ) -> tuple[Node, bool]:
        existing_node = self.get(key)
        if existing_node:
            return existing_node, False

        new_node = node_factory()
        self._registry[key] = new_node
        return new_node, True
