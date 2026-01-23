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
from cascade.bus.events import ResourceAcquired, ResourceReleased

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

        # Prepare Inputs
        # pos_inputs: index -> value
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        # kw_inputs: name -> value (mutable, we will pop from it)
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        final_args: List[Any] = []
        final_kwargs: Dict[str, Any] = {}

        next_pos_idx = 0

        for param in sig.parameters.values():
            # --- 1. Special Handling: Inject / System Context ---
            # These are handled regardless of Parameter Kind (except maybe VAR_*)
            injected_value = None
            has_injection = False

            if param.name == "params_context":
                injected_value = self.context.params
                has_injection = True
            elif isinstance(param.default, Inject):
                injected_value = self._resolve_resource(param.default, stack)
                has_injection = True

            if has_injection:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    final_args.append(injected_value)
                elif param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    final_kwargs[param.name] = injected_value
                # VAR_POSITIONAL / VAR_KEYWORD usually don't have Inject defaults, ignoring.
                continue

            # --- 2. Standard Parameter Handling ---

            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                # Must take from positional inputs
                if next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    final_args.append(param.default)
                else:
                    # Let Python raise the error if missing
                    pass

            elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                # Priority: Keyword -> Positional
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                elif next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    # Python will use default
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:  # *args
                # Consume ALL remaining positional inputs
                # We need to find all keys >= next_pos_idx
                sorted_keys = sorted(
                    [k for k in pos_inputs.keys() if k >= next_pos_idx]
                )
                for k in sorted_keys:
                    final_args.append(pos_inputs[k])
                # Advance index to avoid re-consumption
                if sorted_keys:
                    next_pos_idx = sorted_keys[-1] + 1

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                # else default or error

            elif param.kind == inspect.Parameter.VAR_KEYWORD:  # **kwargs
                # Consume ALL remaining keyword inputs
                # kw_inputs is being popped, so whatever is left goes here
                final_kwargs.update(kw_inputs)
                kw_inputs.clear()

        return final_args, final_kwargs

    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        provider = self.context.resource_container.get_provider(name)

        # 3. Recursively Resolve Dependencies for the Provider
        sig = inspect.signature(provider)
        deps = {}
        for param_name, param in sig.parameters.items():
            if isinstance(param.default, Inject):
                deps[param_name] = self._resolve_resource(param.default, stack)

        # Access bus for event publishing
        # ResourceContainer has the bus, and Context has the container
        bus = getattr(self.context.resource_container, "bus", None)
        run_id = self.context.run_id

        # 4. Instantiate
        resource = None
        if inspect.isgeneratorfunction(provider):
            gen = provider(**deps)
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")
                
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))

            stack.callback(cleanup)
            return resource
        else:
            resource = provider(**deps)
            
            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Even for non-generators, we register a callback to emit the Released event
            # when the scope (stack) exits.
            def cleanup_event():
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))
            
            stack.callback(cleanup_event)
            return resource
