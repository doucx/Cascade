from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Protocol,
)

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
# We use Any for Node/Graph here to avoid a circular dependency with the legacy execution-graph package.
ExecutionPlan = List[List[Any]]


class Solver(Protocol):
    def resolve(self, graph: Any) -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: Any,
        callable_obj: Callable,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any: ...


class CacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...


class CachePolicy(Protocol):
    async def check(self, task_id: str, inputs: dict[str, Any]) -> Any: ...

    async def save(self, task_id: str, inputs: dict[str, Any], output: Any) -> None: ...


class StateBackend(Protocol):
    async def put_result(self, node_id: str, result: Any) -> None: ...

    async def get_result(self, node_id: str) -> Any | None: ...

    async def has_result(self, node_id: str) -> bool: ...

    async def mark_skipped(self, node_id: str, reason: str) -> None: ...

    async def get_skip_reason(self, node_id: str) -> str | None: ...

    async def clear(self) -> None: ...


class SubscriptionHandle(Protocol):
    async def unsubscribe(self) -> None: ...


class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...


class Provider(Protocol):
    name: str

    def create_factory(self) -> LazyFactory: ...


class Connector(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def publish(
        self, topic: str, payload: dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None: ...

    async def subscribe(
        self, topic: str, callback: Callable[[str, dict], Awaitable[None]]
    ) -> SubscriptionHandle: ...
