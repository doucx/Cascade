from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.context import ExpansionContext


class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        """
        Creates global infrastructure for this resource type (e.g., Allocator, Ledger).
        Called once per resource type during the global setup phase.
        """
        ...

    def expand_task(
        self,
        ctx: ExpansionContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        """
        Phase 1: Materialization.
        Creates the physical nodes required for a task to consume this resource
        (e.g., Requestor, Amount Constant).
        MUST NOT create any connections.
        """
        ...

    def wire_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        """
        Phase 2: Wiring.
        Connects the nodes created in Phase 1 to the task's triad and the
        global resource infrastructure.
        MUST NOT create any new nodes.
        """
        ...