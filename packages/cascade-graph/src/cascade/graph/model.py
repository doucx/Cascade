from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.ir.models import TaskDef


class EdgeType(Enum):
    DATA = auto()
    CONDITION = auto()
    CONSTRAINT = auto()
    IMPLICIT = auto()
    SEQUENCE = auto()
    ROUTER_ROUTE = auto()
    POTENTIAL = auto()
    ITERATIVE_JUMP = auto()


@dataclass
class Node:
    # Stable identifier for the node instance in the graph.
    # Computed from TaskDef fingerprint + Instance configuration (bindings, policies)
    structural_id: str

    # The static definition of the task.
    # Single Source of Truth for name, signature, mode, etc.
    definition: TaskDef

    # The actual python executable object.
    # This is NOT part of the definition (it's runtime state), but checked here for convenience.
    callable_obj: Optional[Callable] = None

    # Node-specific type ("task", "map", "param") - might be merged into definition later?
    # For now, it distinguishes how the definition is APPLIED.
    node_type: str = "task"

    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Mapping logic (only for node_type='map')
    mapping_factory: Optional[Any] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization flag
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # SHORTCUT for debugging/logging, but code should prefer definition.name where possible
        return self.definition.name


@dataclass
class Edge:
    source: Node
    target: Node
    arg_name: str
    edge_type: EdgeType = EdgeType.DATA
    router: Optional[Any] = None
    jump_selector: Optional[Any] = None


@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.structural_id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.structural_id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
