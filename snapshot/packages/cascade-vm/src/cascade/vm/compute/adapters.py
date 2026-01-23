import asyncio
import inspect
import logging
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.dsl.resources import Inject
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext

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
        context: ExecutionContext,
        wakeup_event: Optional[asyncio.Event] = None,
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
                raw_inputs: Dict[str, Any] = {
                    key: self.store.get(ref) for key, ref in request.input_refs.items()
                }

                # 2. Resolve Code
                func = self.registry.get(request.code_hash)

                # 3. Smart Binding & Injection
                args, kwargs = self._bind_execution_arguments(func, raw_inputs, stack)

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

    def _bind_execution_arguments(
        self, func: Any, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        sig = inspect.signature(func)
        final_kwargs: Dict[str, Any] = {}

        # Pre-process inputs
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        for i, param in enumerate(sig.parameters.values()):
            # A. Try Keyword Input
            if param.name in kw_inputs:
                final_kwargs[param.name] = kw_inputs[param.name]
                continue

            # B. Try Positional Input
            if i in pos_inputs:
                final_kwargs[param.name] = pos_inputs[i]
                continue

            # C. System Context
            if param.name == "params_context":
                final_kwargs[param.name] = self.context.params
                continue

            # D. Dependency Injection
            if isinstance(param.default, Inject):
                final_kwargs[param.name] = self._resolve_resource(param.default, stack)
                continue

            # E. Default Value (implicitly handled by Python call if missing from final_kwargs)

        # Split into args/kwargs to respect POSITIONAL_ONLY
        call_args = []
        call_kwargs = {}

        for param in sig.parameters.values():
            if param.name in final_kwargs:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    call_args.append(final_kwargs[param.name])
                else:
                    call_kwargs[param.name] = final_kwargs[param.name]

        return call_args, call_kwargs

    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        # Note: We assume task-scoped resources here don't have complex recursive dependencies
        # for this adaptation layer.
        provider = self.context.resource_container.get_provider(name)

        if inspect.isgeneratorfunction(provider):
            gen = provider()
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")

            stack.callback(cleanup)
            return resource
        else:
            return provider()
