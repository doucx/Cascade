from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Token:
    """
    The fundamental unit of energy and information flow in the physics field.
    """

    payload: Any
    """The actual data being transferred (Business Value)."""

    tag: str = "default"
    """Routing tag used by Channels to filter tokens (Control Signal)."""

    trace: Dict[str, Any] = field(default_factory=dict)
    """
    Metadata accumulator for observability and context propagation.
    Contains timestamp, source_id, retry_counts, etc.
    """


@dataclass
class PhysicsNode:
    """
    Base class for all static entities in the bipartite graph.
    """

    id: str
    """
    The canonical structural identifier.
    Naming Convention: [State]_[Source]_[Object]_hash
    """

    name: str
    """Human-readable name for debugging and visualization."""


@dataclass
class PhysicsDataNode(PhysicsNode):
    """
    Represents a storage location (Place) in the Petri net.
    It holds Tokens.
    """

    capacity: int = 1
    """Maximum number of tokens this node can hold simultaneously."""


@dataclass
class PhysicsFuncNode(PhysicsNode):
    """
    Represents a transformation unit (Transition) in the Petri net.
    It consumes Tokens from inputs and produces Tokens to outputs.
    """

    input_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""

    output_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""
