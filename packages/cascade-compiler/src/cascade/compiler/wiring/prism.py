from typing import Protocol, Any
from cascade.spec.environment import ResourceDef
from cascade.spec.ir.models import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.wiring.context import WiringContext


class ResourcePrism(Protocol):
    """
    A Prism refracts a high-level Resource Definition into a complex physical topology.
    It encapsulates the knowledge of how to wire a specific type of resource.
    """

    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        """
        Create the global infrastructure for this resource (e.g., Allocator, Ledger).
        This may be called multiple times for different resources of the same type.
        """
        ...

    def connect_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        """
        Wire a specific task to request/release this resource.
        """
        ...