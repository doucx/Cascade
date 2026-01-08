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