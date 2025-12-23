from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto
import inspect


from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint


class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""

    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)


@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization: Flag indicating if the node requires complex resolution 
    # (e.g., has Inject markers or complex nested structures in bindings)
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.id)


@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""

    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str
    # The semantic type of this edge
    edge_type: EdgeType = EdgeType.DATA

    # If set, implies this edge is the selector for a dynamic router
    router: Optional[Any] = None


@dataclass
class Graph:
    """A container for nodes and edges representing the workflow topology."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
