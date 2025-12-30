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
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    # The static definition of the task.
    definition: TaskDef

    # Optional legacy type tag ("task", "map", "param").
    # Prefer isinstance checks over this string.
    node_type: str = "task"

    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    # Maps argument names (or indices) to literal values.
    # For TaskNode, this holds arguments.
    # For ParamNode, this is usually empty or holds raw config.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization flag for Resolvers
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        return self.definition.name


@dataclass
class TaskNode(Node):
    """Represents a standard executable task."""

    # The actual python executable object.
    _callable: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""

    # The key to look up in the parameters dictionary
    param_key: str = ""

    # Note: We do NOT store ParamSpec here. The spec is a definition-time artifact.
    # The Node only cares about the runtime key.


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