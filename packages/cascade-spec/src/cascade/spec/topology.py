from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .physics import PhysicsNode


@dataclass
class Channel:
    """
    A directed connection between a Function Node and a Data Node.
    """

    source_node_id: str
    """The ID of the upstream node."""

    source_port: str
    """The name of the output port on the source node."""

    target_node_id: str
    """
    The ID of the downstream node.
    Note: In a bipartite graph, if Source is Func, Target MUST be Data.
    """

    tag_filter: Optional[str] = None
    """
    If set, this channel only accepts Tokens with a matching tag.
    This acts as a spectral filter for control flow.
    """


@dataclass
class BipartiteGraph:
    """
    The static, physical representation of the computational field.
    """

    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    """All physical nodes indexed by their ID."""

    channels: List[Channel] = field(default_factory=list)
    """All connections between nodes."""
