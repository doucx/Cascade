import inspect
from typing import Any, Dict, List
from cascade.graph.model import Node


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
            return await node.callable_obj(*args, **kwargs)
        else:
            return node.callable_obj(*args, **kwargs)
