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
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any: ...


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
