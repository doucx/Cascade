import asyncio
import functools
from typing import Callable, Any, Tuple
from concurrent.futures import ThreadPoolExecutor


class PhysicsExecutor:
    def __init__(self):
        # The ThreadPoolExecutor's finalizer handles shutdown on garbage collection.
        self._thread_pool = ThreadPoolExecutor(thread_name_prefix="cascade_physics")

    async def submit(self, func: Callable, args: Tuple) -> Any:
        loop = asyncio.get_running_loop()

        # functools.partial is used because run_in_executor doesn't directly
        # support passing arguments to the target function.
        func_to_run = functools.partial(func, *args)

        # This awaits the future returned by run_in_executor,
        # effectively pausing this coroutine without blocking the event loop.
        result = await loop.run_in_executor(self._thread_pool, func_to_run)
        return result
