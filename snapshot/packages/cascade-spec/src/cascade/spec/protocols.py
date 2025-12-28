from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable
from cascade.graph.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List[Node]]


class Solver(Protocol):
    def resolve(self, graph: Graph) -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: Node,
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


class SubscriptionHandle(Protocol):
    async def unsubscribe(self) -> None: ...


class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...


class Connector(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None: ...

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle": ...
