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

    # Node-specific type ("task", "map", "param")
    # Kept for serialization and legacy checks, but logic should prefer isinstance.
    node_type: str = "task"

    # Instance-specific configuration common to most executable nodes
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def callable_obj(self) -> Optional[Callable]:
        """Polymorphic accessor for the executable object."""
        return None


@dataclass
class TaskNode(Node):
    """Represents a standard executable task."""

    # The actual python executable object.
    _callable: Optional[Callable] = None
    
    # Optimization flag
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""
    
    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec
    param_spec: Optional[ParamSpec] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # Param nodes use a special internal task to retrieve values
        from cascade.internal.inputs import _get_param_value
        return _get_param_value.func


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
