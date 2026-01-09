from typing import Protocol
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext


class ExpansionPolicy(Protocol):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        """
        Expands a logical node by creating and adding new physical nodes
        to its corresponding subgraph.

        This phase is strictly for MATERIALIZATION. Implementations of this
        protocol are FORBIDDEN from creating channels between different
        subgraphs.
        """
        ...