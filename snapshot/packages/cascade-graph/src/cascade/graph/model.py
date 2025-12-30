from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.ir.models import TaskDef
from cascade.spec.input import ParamSpec


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
    """Base class for all nodes in the computation graph."""

    structural_id: str
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # Provide a safe fallback for the node's name
        return self.structural_id

    @property
    def node_type(self) -> str:
        raise NotImplementedError("Subclasses must define a node_type property.")


@dataclass
class TaskNode(Node):
    """Represents a standard computation task."""

    definition: TaskDef
    callable_obj: Callable
    input_bindings: Dict[str, Any] = field(default_factory=dict)
    has_complex_inputs: bool = False

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def node_type(self) -> str:
        return "task"


@dataclass
class MapNode(Node):
    """Represents a .map() operation over a factory."""

    definition: TaskDef
    mapping_factory: Any
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        # For map nodes, the name reflects the mapping operation.
        return f"map({self.definition.name})"

    @property
    def node_type(self) -> str:
        return "map"


@dataclass
class ParamNode(Node):
    """Represents a cs.Param, a special input node."""

    param_spec: ParamSpec
    # It still has a definition because it's created from a task (_get_param_value)
    definition: TaskDef
    callable_obj: Callable

    @property
    def name(self) -> str:
        return self.param_spec.name

    @property
    def node_type(self) -> str:
        return "param"


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