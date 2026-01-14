from typing import (
    Protocol,
    List,
    Any,
    Dict,
    Optional,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    # Avoid circular dependency with implementation-heavy contexts
    # These will be passed as 'Any' or via Generic types in the implementation
    pass

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
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...


class CacheBackend(Protocol):
    async def get(self, key: str) -> Optional[Any]: ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: ...


class CachePolicy(Protocol):
    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any: ...

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None: ...


class StateBackend(Protocol):
    async def put_result(self, node_id: str, result: Any) -> None: ...

    async def get_result(self, node_id: str) -> Optional[Any]: ...

    async def has_result(self, node_id: str) -> bool: ...

    async def mark_skipped(self, node_id: str, reason: str) -> None: ...

    async def get_skip_reason(self, node_id: str) -> Optional[str]: ...

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
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None: ...

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle": ...
