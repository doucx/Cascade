import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from .contract import ComputeRequest

logger = logging.getLogger(__name__)


@dataclass
class ProxyDef:
    is_async: bool
    mode: str = "blocking"


@dataclass
class ProxyNode:
    name: str
    definition: ProxyDef
    node_type: str = "task"


class BridgedComputeService:
    def __init__(
        self,
        executor: Executor,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.executor = executor
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._wakeup_event = wakeup_event
        self._running = False
        self._active_count = 0

    @property
    def active_count(self) -> int:
        return self._active_count

    def is_idle(self) -> bool:
        return self.inbound_queue.empty() and self._active_count == 0

    async def run(self) -> None:
        self._running = True
        logger.info("BridgedComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                self._active_count += 1
                asyncio.create_task(self._process_request(request))
        finally:
            logger.info("BridgedComputeService stopped.")

    def stop(self) -> None:
        self._running = False

    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            # 1. Resolve Inputs (Dereference Refs)
            # The ObjectStore protocol dictates that get() returns the actual object.
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Construct Proxy Node for Executor
            # We inspect the function to determine execution properties
            is_async = inspect.iscoroutinefunction(func)

            # If the function is wrapped by @task, it might have a 'mode' attribute
            mode = getattr(func, "mode", "blocking")
            name = getattr(func, "__name__", "unknown_task")

            proxy_node = ProxyNode(
                name=name, definition=ProxyDef(is_async=is_async, mode=mode)
            )

            # 4. Delegate Execution to Runtime Executor
            # This allows the Runtime to manage thread pools, constraints, etc.
            result = await self.executor.execute(proxy_node, func, args, kwargs)  # type: ignore

        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            result = e
        finally:
            self._active_count -= 1

        # 5. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 6. Report Completion
        await self.outbound_queue.put((request.reply_to_nid, result_token))

        # 7. Signal Wakeup
        if self._wakeup_event:
            self._wakeup_event.set()

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Helper to convert dict inputs back to *args and **kwargs
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
