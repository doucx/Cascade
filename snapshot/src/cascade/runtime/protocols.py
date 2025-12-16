from typing import Protocol, List, Any, Dict
from cascade.graph.model import Graph, Node

# An execution plan is simply an ordered list of nodes to execute.
ExecutionPlan = List[Node]


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
