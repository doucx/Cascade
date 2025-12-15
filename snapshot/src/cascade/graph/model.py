from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any


@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    callable_obj: Callable
    
    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None

    def __hash__(self):
        return hash(self.id)


@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""

    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str


@dataclass
class Graph:
    """A container for nodes and edges representing the workflow."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
