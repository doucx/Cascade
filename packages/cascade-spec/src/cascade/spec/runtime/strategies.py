from typing import Protocol, Any, Dict
from dataclasses import dataclass, field
from contextlib import ExitStack
from cascade.spec.runtime.interfaces import StateBackend
from cascade.spec.runtime.storage import ObjectStore


@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    object_store: ObjectStore
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)


class ExecutionStrategy(Protocol):
    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any: ...
