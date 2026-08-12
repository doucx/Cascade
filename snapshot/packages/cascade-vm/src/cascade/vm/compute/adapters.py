from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import ExitStack
from dataclasses import dataclass

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime import ComputeRequest, ExecutionContext
from cascade.spec.runtime.interfaces import Executor
from cascade.spec.runtime.storage import ObjectStore

from ..registry import CodeRegistry
from .binding import SignatureBinder

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
        inbound_queue: asyncio.Queue[ComputeRequest],
        outbound_queue: asyncio.Queue[tuple[str, Token]],
        context: ExecutionContext,
        wakeup_event: asyncio.Event | None = None,
    ):
        self.executor = executor
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.context = context
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
            with ExitStack() as stack:
                # 1. Resolve Inputs (Dereference Refs)
                # The request now carries pre-separated args and kwargs
                resolved_args = [self.store.get(ref) for ref in request.input_args]
                resolved_kwargs = {
                    key: self.store.get(ref)
                    for key, ref in request.input_kwargs.items()
                }

                # 2. Resolve Code
                func = self.registry.get(request.code_hash)

                # 3. Smart Binding & Injection
                binder = SignatureBinder(func, self.context)
                args, kwargs = binder.bind_and_resolve(
                    resolved_args, resolved_kwargs, stack
                )

                # 4. Construct Proxy Node
                is_async = inspect.iscoroutinefunction(func)
                mode = getattr(func, "mode", "blocking")
                name = getattr(func, "__name__", "unknown_task")

                proxy_node = ProxyNode(
                    name=name, definition=ProxyDef(is_async=is_async, mode=mode)
                )

                # 5. Delegate Execution
                result = await self.executor.execute(proxy_node, func, args, kwargs)  # type: ignore

        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            result = e
        finally:
            self._active_count -= 1

        # 6. Store Result and Report
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        await self.outbound_queue.put((request.reply_to_nid, result_token))

        if self._wakeup_event:
            self._wakeup_event.set()
