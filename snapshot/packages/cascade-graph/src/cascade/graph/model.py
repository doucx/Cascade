from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.ir.models import TaskDef

# We store the ParamSpec here explicitly for type safety
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
    # Stable identifier for the node instance in the graph.
    current_node_instance_hash: str

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
    has_complex_inputs: bool = False
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.current_node_instance_hash == other.current_node_instance_hash

    def __hash__(self):
        return hash(self.current_node_instance_hash)

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def callable_obj(self) -> Optional[Callable]:
        return None


@dataclass(eq=False)
class TaskNode(Node):
    # The actual python executable object.
    _callable: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass(eq=False)
class MapNode(Node):
    mapping_factory: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory


@dataclass(eq=False)
class ParamNode(TaskNode):
    param_spec: Optional[ParamSpec] = None
    has_complex_inputs: bool = True

    # Inherits callable_obj property from TaskNode


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
        if node.current_node_instance_hash not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.current_node_instance_hash] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
