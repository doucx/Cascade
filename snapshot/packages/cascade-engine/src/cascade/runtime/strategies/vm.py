import asyncio
from contextlib import ExitStack
from typing import Any, Dict

from cascade.spec.protocols import StateBackend
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.vm import VirtualMachine
from cascade.vm.middleware.standard import (
    ArgumentResolutionMiddleware, 
    ConstraintMiddleware, 
    ResourceLifecycleMiddleware, 
    RetryMiddleware
)
from cascade.vm.middleware.observability import ObservabilityMiddleware
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall
from cascade.spec.jump import Jump
from typing import List, Optional


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target
        next_input_overrides: Optional[Dict[str, Any]] = None
        local_compilation_cache: Dict[str, Any] = {}

        while True:
            # 1. Compilation Stage (with caching)
            if current_target._uuid in local_compilation_cache:
                compilation_result, blueprint = local_compilation_cache[current_target._uuid]
            else:
                compilation_result = Frontend.compile(current_target)
                graph_ir = compilation_result.ir
                execution_plan = Optimizer.optimize(graph_ir)
                blueprint = Backend.compile(graph_ir, execution_plan)
                local_compilation_cache[current_target._uuid] = (compilation_result, blueprint)

            # 2. Prepare Inputs for this Iteration
            # Start with static bindings from the LazyResult
            if isinstance(current_target, MappedLazyResult):
                initial_args: List[Any] = []
                initial_kwargs: Dict[str, Any] = dict(current_target.mapping_kwargs)
            else:
                initial_args = list(current_target.args)
                initial_kwargs = dict(current_target.kwargs)

            # Apply overrides from the previous Jump signal
            if next_input_overrides:
                for key, value in next_input_overrides.items():
                    if key.isdigit():
                        idx = int(key)
                        while len(initial_args) <= idx:
                            initial_args.append(None)
                        initial_args[idx] = value
                    else:
                        initial_kwargs[key] = value
                next_input_overrides = None  # Consume overrides

            # 3. VM Execution
            vm = VirtualMachine(
                resource_manager=self.resource_manager,
                constraint_manager=self.constraint_manager,
                wakeup_event=self.wakeup_event,
            )
            
            vm.set_middlewares([
                ObservabilityMiddleware(self.bus, run_id),
                RetryMiddleware(),
                ConstraintMiddleware(self.constraint_manager),
                ResourceLifecycleMiddleware(self.resource_manager),
                ArgumentResolutionMiddleware(active_resources, params),
            ])

            result = await vm.execute(
                blueprint,
                symbol_table=compilation_result.symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 4. Result Interpretation (The Trampoline Logic)
            if isinstance(result, Jump):
                selector = getattr(current_target, '_jump_selector', None)
                if not selector:
                    raise RuntimeError(
                        f"Task '{current_target.task.name}' returned a Jump signal but has no bound 'select_jump'."
                    )
                
                next_target = selector.routes.get(result.target_key)
                
                if next_target is None:
                    # Loop exit condition (e.g., jump_selector has {'exit': None})
                    return result.data
                
                # Prepare for the next iteration
                current_target = next_target
                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    # Positional override for single return value
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}
                
                # Continue to the next loop iteration
                continue
            else:
                # Normal termination, not a Jump signal
                return result