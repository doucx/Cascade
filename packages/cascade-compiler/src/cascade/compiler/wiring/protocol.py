from typing import Protocol
from cascade.spec.ir.models import NodeIR
from cascade.compiler.backend.expander import SubGraph
from .context import WiringContext


class WiringPolicy(Protocol):
    """
    Protocol for a wiring strategy.
    Each policy is responsible for a specific aspect of the physical graph construction.
    """

    def setup_globals(self, ctx: WiringContext) -> None:
        """
        Phase 0: Setup global infrastructure.
        Called once before processing any nodes.
        Used for creating global resource brokers, observability buses, etc.
        """
        ...

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        """
        Phase 1: Wire a specific node.
        Called for each node in the logical graph.
        Used for connecting the node's triad to inputs, outputs, resources, etc.
        """
        ...