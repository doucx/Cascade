import asyncio
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

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            # Implicit Offloading:
            # Synchronous tasks are offloaded to a separate thread to prevent blocking
            # the main asyncio event loop. This allows async tasks and IO operations
            # to run concurrently with CPU-bound or blocking sync tasks.
            result = await asyncio.to_thread(node.callable_obj, *args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
