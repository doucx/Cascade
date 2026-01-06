import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.contract import ComputeRequest

logger = logging.getLogger(__name__)


class LocalComputeService:
    def __init__(
        self,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
    ):
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False
        self._active_count = 0

    def put_nowait(self, request: ComputeRequest) -> None:
        """
        Submit a request to the service. 
        Increments active count immediately to prevent idle-detection race conditions.
        Matches the asyncio.Queue interface expected by standard_dispatcher.
        """
        self._active_count += 1
        self.inbound_queue.put_nowait(request)

    def is_idle(self) -> bool:
        # Since active_count covers both "in queue" and "processing", 
        # we only need to check this counter.
        return self._active_count == 0

    async def run(self) -> None:
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Active count was already incremented in put_nowait
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")

    def stop(self) -> None:
        self._running = False
        # To unblock the `run` loop, we can put a sentinel value,
        # but for now, we assume the managing task will be cancelled.

    async def _process_request(self, request: ComputeRequest) -> None:
        # Note: self._active_count is incremented in run() before calling this
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Execute
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            # Per v3.1 spec, exceptions are treated as values
            result = e

        try:
            # 4. Store Result and Prepare Token
            result_ref = self.store.put(result)
            result_token = Token(payload=result_ref, trace=request.trace)

            # 5. Report Completion to Outbound Queue
            await self.outbound_queue.put((request.reply_to_nid, result_token))
        finally:
            self._active_count -= 1

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
