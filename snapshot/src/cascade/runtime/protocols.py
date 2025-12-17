from typing import Protocol, List, Any, Dict
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


class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...


class StateBackend(Protocol):
    """
    Protocol for a backend that stores the transient state of a single workflow run.
    This includes task results and skip statuses.
    """

    def put_result(self, node_id: str, result: Any) -> None:
        """Stores the result of a completed task."""
        ...

    def get_result(self, node_id: str) -> Optional[Any]:
        """Retrieves the result of a task. Returns None if not found."""
        ...

    def has_result(self, node_id: str) -> bool:
        """Checks if a result for a given task ID exists."""
        ...

    def mark_skipped(self, node_id: str, reason: str) -> None:
        """Marks a task as skipped."""
        ...

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        """Retrieves the reason a task was skipped. Returns None if not skipped."""
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
