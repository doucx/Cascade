from typing import Protocol, Any, TYPE_CHECKING
from cascade.spec.ir.graph import NodeIR
from cascade.spec.compiler.model import SubGraph

if TYPE_CHECKING:
    # Avoid circular dependency with implementation-heavy contexts
    # These will be passed as 'Any' or via Generic types in the implementation
    from cascade.compiler.backend.expansion.context import ExpansionContext
    from cascade.compiler.backend.wiring.context import WiringContext
    from cascade.spec.physical.environment import ResourceDef

class ExpansionPolicy(Protocol):
    def expand(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...

class WiringPolicy(Protocol):
    def setup_globals(self, ctx: Any) -> None: ...
    def apply(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...

class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: Any, res_def: Any) -> None: ...
    def expand_task(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any) -> None: ...
    def wire_task(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any) -> None: ...