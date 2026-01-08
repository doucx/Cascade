## [WIP] 好的，我们开始实施 **阶段一：定义核心抽象 (The Abstractions)**。

这一步我们将引入两个关键的构建块：
1.  **`PhysicalBlock`**: 一个自包含的物理拓扑单元，具有明确的 I/O 边界。这将取代（并最终包含）旧的 `SubGraph`。
2.  **`TopologyTransform`**: 一个统一的接口，用于将逻辑 IR 转换为物理 Block（展开），或将一个 Block 包裹在另一个 Block 中（修饰）。

这两个文件将作为后续重构的基石。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/block.py
~~~~~
~~~~~python
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
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/transform.py
~~~~~
~~~~~python
from typing import Protocol, Optional

from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.block import PhysicalBlock


class TopologyTransform(Protocol):
    """
    Protocol for any component that participates in the expansion pipeline.

    Unifies the concepts of 'Expander' (creation) and 'WiringPolicy' (decoration).
    """

    def apply(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        inner_block: Optional[PhysicalBlock] = None,
    ) -> PhysicalBlock:
        """
        Applies a topological transformation.

        Args:
            ctx: The global wiring context (for accessing environment, resource defs, etc).
            node_ir: The logical node definition being expanded.
            inner_block: The block produced by the previous step in the pipeline.
                         If None, this transform is responsible for creating the initial block
                         (e.g., the Base Triad).

        Returns:
            A new PhysicalBlock.
            - If acting as a Base Expander, returns the generated Triad.
            - If acting as a Wrapper (e.g. Retry), returns a new block containing the inner_block
              plus new control nodes, with updated Entry/Exit ports.
        """
        ...
~~~~~
