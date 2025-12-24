import inspect
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """



    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if inspect.iscoroutinefunction(node.callable_obj):
            result = await node.callable_obj(*args, **kwargs)
        else:
            result = node.callable_obj(*args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
