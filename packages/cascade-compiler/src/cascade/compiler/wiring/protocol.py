from typing import Protocol
from cascade.spec.ir.models import NodeIR
from cascade.compiler.backend.expander import SubGraph
from .context import WiringContext


class WiringPolicy(Protocol):
    def setup_globals(self, ctx: WiringContext) -> None: ...

    def apply(
        self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None: ...
