from dataclasses import dataclass, field
from typing import Any, List, Dict, Protocol, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from cascade.spec.blueprint import Instruction, Call, MapCall
    from cascade.vm.machine import Frame

# Handler Type: A function that takes context and returns an Awaitable result
# NextHandler Type: A function that takes no args (context is implicit/closed) and returns Awaitable result
NextHandler = Callable[[], Awaitable[Any]]


@dataclass
class ExecutionContext:
    """
    Carries the state of a single instruction execution through the middleware pipeline.
    """
    vm: "VirtualMachine"
    instruction: "Instruction"
    frame: "Frame"
    symbol_table: Dict[str, Callable]
    
    # Execution-scoped context (e.g., user params)
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    # Engine-scoped active resources
    active_resources: Dict[str, Any] = field(default_factory=dict)
    
    # Resolvable inputs. Middleware can modify these in-place.
    resolved_args: List[Any] = field(default_factory=list)
    resolved_kwargs: Dict[str, Any] = field(default_factory=dict)


class Middleware(Protocol):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        ...