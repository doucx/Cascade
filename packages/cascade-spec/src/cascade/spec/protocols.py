from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable
from cascade.graph.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List[Node]]


class Solver(Protocol):
    """
    Protocol for a solver that resolves a graph into an execution plan.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan: ...


class Executor(Protocol):
    """
    Protocol for an executor that runs a single task.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes the node's callable with the provided fully-resolved arguments.
        """
        ...


class CacheBackend(Protocol):
    """
    Protocol for a storage backend that persists cached results.
    """

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves a value by key."""
        ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets a value for a key, optionally with a TTL in seconds."""
        ...


class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...


class StateBackend(Protocol):
    """
    Protocol for a backend that stores the transient state of a single workflow run.
    This includes task results and skip statuses.
    """

    async def put_result(self, node_id: str, result: Any) -> None:
        """Stores the result of a completed task."""
        ...

    async def get_result(self, node_id: str) -> Optional[Any]:
        """Retrieves the result of a task. Returns None if not found."""
        ...

    async def has_result(self, node_id: str) -> bool:
        """Checks if a result for a given task ID exists."""
        ...

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        """Marks a task as skipped."""
        ...

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        """Retrieves the reason a task was skipped. Returns None if not skipped."""
        ...


class SubscriptionHandle(Protocol):
    """
    A handle to an active subscription, allowing it to be cancelled.
    """

    async def unsubscribe(self) -> None:
        """Cancels the subscription."""
        ...


class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """

    def map(self, **kwargs) -> Any:
        """
        Creates a mapped lazy result by applying this factory over iterables.
        """
        ...


class Connector(Protocol):
    """
    Protocol for a connector that bridges the Cascade runtime with the outside world.
    It's responsible for all non-business-logic I/O, primarily for telemetry and control.
    """

    async def connect(self) -> None:
        """Establishes a connection to the external system (e.g., MQTT Broker)."""
        ...

    async def disconnect(self) -> None:
        """Disconnects from the external system and cleans up resources."""
        ...

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        """Publishes a message (e.g., a telemetry event) to a specific topic."""
        ...

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle":
        """
        Subscribes to a topic to receive messages (e.g., control commands).
        Returns a handle that can be used to unsubscribe.
        """
        ...
