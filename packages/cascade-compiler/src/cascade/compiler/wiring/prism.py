from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.wiring.context import WiringContext


class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None: ...

    def connect_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None: ...
