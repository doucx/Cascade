from dataclasses import dataclass, field
from typing import Any, List, Dict, Protocol, Callable, Awaitable, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cascade.spec.blueprint import Instruction
    from cascade.vm.machine import Frame

# Handler Type: A function that takes no args (context is implicit/closed over) and returns Awaitable result
NextHandler = Callable[[], Awaitable[Any]]


@dataclass
class ExecutionContext:
    """
    Carries the state of a single instruction execution through the middleware pipeline.
    """
    instruction: "Instruction"
    frame: "Frame"
    symbol_table: Dict[str, Callable]
    
    # Resolvable inputs. Middleware can modify these in-place.
    # The pipeline starts with these populated from the instruction's operands.
    resolved_args: List[Any] = field(default_factory=list)
    resolved_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Shared storage for middlewares to pass data down the line (e.g. dynamic constraints)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Middleware(Protocol):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        ...