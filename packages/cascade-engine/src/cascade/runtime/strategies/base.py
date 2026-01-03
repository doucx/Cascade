from typing import Protocol, Any, Dict
from dataclasses import dataclass, field
from contextlib import ExitStack
from cascade.spec.protocols import StateBackend


@dataclass
class ExecutionContext:
    """
    Encapsulates the runtime context required for a strategy to execute a workflow.
    """

    run_id: str
    state_backend: StateBackend
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)


class ExecutionStrategy(Protocol):
    """
    Protocol defining a strategy for executing a workflow target.
    """

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any: ...