from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto
from abc import ABC

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
class Node(ABC):
    """Abstract base class for all nodes in the computation graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # Each subclass must provide a way to get its name.
        raise NotImplementedError


@dataclass
class TaskNode(Node):
    """Represents a standard computation task."""

    # The static definition of the task.
    definition: TaskDef
    # The actual python executable object.
    callable_obj: Optional[Callable]
    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None
    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)
    # Optimization flag
    has_complex_inputs: bool = False

    @property
    def name(self) -> str:
        return self.definition.name


@dataclass
class MapNode(Node):
    """Represents a .map() operation over a factory."""

    # The static definition of the task factory being mapped.
    definition: TaskDef
    # The task factory to be called for each item.
    mapping_factory: Any
    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None
    # Structural Bindings (Literals) for the map call itself.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"map({self.definition.name})"


@dataclass
class ParamNode(Node):
    """Represents a cs.Param, a runtime input source."""

    # The specification of the parameter.
    param_spec: ParamSpec

    @property
    def name(self) -> str:
        return f"param({self.param_spec.name})"


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