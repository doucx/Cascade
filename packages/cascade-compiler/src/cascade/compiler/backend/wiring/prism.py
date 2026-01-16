from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from ..expander import SubGraph
from .context import WiringContext
from ..expansion.context import ExpansionContext


class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None: ...

    def expand_task(
        self,
        ctx: ExpansionContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None: ...

    def wire_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None: ...
