import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    def __init__(self):
        # NOTE: These executors are created per-engine-run.
        # Their lifecycle is tied to the LocalExecutor instance.
        # Python's ThreadPoolExecutor finalizer handles shutdown on garbage collection.
        self._blocking_executor = ThreadPoolExecutor(
            thread_name_prefix="cascade_blocking"
        )
        self._compute_executor = ThreadPoolExecutor(
            thread_name_prefix="cascade_compute"
        )

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()

            # Select the appropriate executor based on the task's declared mode
            if node.execution_mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor

            # Use functools.partial to handle keyword arguments, as
            # run_in_executor only accepts positional arguments for the target function.
            func_to_run = functools.partial(node.callable_obj, *args, **kwargs)
            result = await loop.run_in_executor(executor, func_to_run)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
