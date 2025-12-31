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
        from cascade.spec.jump import Jump

        current_target = target
        next_args_override: Optional[List[Any]] = None
        next_kwargs_override: Optional[Dict[str, Any]] = None

        while True:
            # 1. Compile (every loop, as target object might change)
            compilation_result = Frontend.compile(current_target)
            graph_ir = compilation_result.ir
            symbol_table = compilation_result.symbol_table
            execution_plan = Optimizer.optimize(graph_ir)
            blueprint = Backend.compile(graph_ir, execution_plan)

            # 2. Prepare VM and Middleware
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

            # 3. Prepare Inputs for this iteration
            # Start with the original args/kwargs from the LazyResult
            initial_args = list(getattr(current_target, 'args', []))
            initial_kwargs = getattr(current_target, 'kwargs', {}).copy()

            # Apply overrides from the previous Jump
            if next_args_override is not None:
                initial_args = next_args_override
            if next_kwargs_override is not None:
                initial_kwargs.update(next_kwargs_override)
            
            # Clear overrides for the next potential loop
            next_args_override, next_kwargs_override = None, None

            # 4. Execute
            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 5. Check for Control Flow Signal
            if not isinstance(result, Jump):
                return result  # Normal termination

            # 6. Handle Explicit Jump
            selector = getattr(current_target, '_jump_selector', None)
            if not selector:
                raise RuntimeError(
                    f"Task '{current_target.task.name}' returned a Jump signal "
                    "but has no bound jump selector. Use cs.bind() to link a selector."
                )

            next_lazy_result = selector.routes.get(result.target_key)

            if next_lazy_result is None:
                return result.data  # Loop exit condition

            # 7. Prepare for next iteration
            current_target = next_lazy_result
            if isinstance(result.data, dict):
                next_kwargs_override = result.data
            elif result.data is not None:
                # Assume single value maps to the first positional argument
                next_args_override = [result.data]