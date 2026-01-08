from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, NamedTuple

from cascade.spec.physical.nodes import PhysicsNode
from cascade.spec.physical.topology import Channel


class PortRef(NamedTuple):
    """
    A reference to a specific port on a specific node within a block.
    Used to define the I/O boundary of a PhysicalBlock.
    """

    node_id: str
    port_name: str


@dataclass
class PhysicalBlock:
    """
    A self-contained unit of physical topology.

    Unlike a raw list of nodes, a PhysicalBlock defines a clear boundary via
    Entry and Exit ports, allowing blocks to be nested and composed.

    It represents the physical realization of a logical concept (e.g., a Task,
    a Retry Loop, a Resource Gate).
    """

    # Internal Topology
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Boundary Interface

    # The primary point where data/control flow enters this block.
    # e.g., The 'worker_input' port of a Bleacher.
    entry: Optional[PortRef] = None

    # The primary point where successful results leave this block.
    # e.g., The 'output_default' port of a Stainer.
    exit: Optional[PortRef] = None

    # For specialized flows (e.g. error paths, sidecars, control signals).
    # Common keys: 'error', 'signal', 'observability'
    ports: Dict[str, PortRef] = field(default_factory=dict)

    def add_node(self, node: PhysicsNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Node ID collision in block: {node.id}")
        self.nodes[node.id] = node

    def add_channel(self, channel: Channel) -> None:
        self.channels.append(channel)

    def merge(self, other: "PhysicalBlock") -> None:
        """
        Absorbs another block into this one.
        Useful when wrapping an inner block.
        """
        self.nodes.update(other.nodes)
        self.channels.extend(other.channels)
        # Note: Merging does NOT automatically update entry/exit ports.
        # The caller (Transform) must decide how the boundary shifts.