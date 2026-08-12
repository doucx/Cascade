from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any, Protocol

from .interfaces import StateBackend
from .storage import ObjectStore


@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    object_store: ObjectStore
    run_stack: ExitStack
    active_resources: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    resource_container: Any = None


class ExecutionStrategy(Protocol):
    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any: ...
