from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Token:
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
    id: str
    """
    The canonical structural identifier.
    Naming Convention: [State]_[Source]_[Object]_hash
    """

    name: str
    """Human-readable name for debugging and visualization."""


@dataclass
class PhysicsDataNode(PhysicsNode):
    capacity: int = 1
    """Maximum number of tokens this node can hold simultaneously."""

    initial_tokens: int = 0
    """Number of tokens to pre-fill at reactor startup (Potential Energy)."""


@dataclass
class PhysicsFuncNode(PhysicsNode):
    input_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""

    output_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""
