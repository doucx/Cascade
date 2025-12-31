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
        from cascade.spec.lazy_types import LazyResult

        current_target = target

        while True:
            # 1. Compile the current target for this iteration
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

            # 3. Execute with current arguments
            # The VM needs to know the initial arguments for this specific run
            initial_args = list(getattr(current_target, 'args', []))
            initial_kwargs = getattr(current_target, 'kwargs', {}).copy()

            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 4. Check for Control Flow Signal
            if not isinstance(result, Jump):
                return result  # Normal termination

            # 5. Handle Explicit Jump
            selector = getattr(current_target, '_jump_selector', None)
            if not selector:
                raise RuntimeError(
                    f"Task '{current_target.task.name}' returned a Jump signal "
                    "but has no bound jump selector. Use cs.bind() to link a selector."
                )

            next_lr_template = selector.routes.get(result.target_key)

            if next_lr_template is None:
                return result.data  # Loop exit condition

            # 6. CRITICAL: Create a NEW LazyResult for the next iteration
            # Start with the original arguments of the next target template
            next_args = list(getattr(next_lr_template, 'args', []))
            next_kwargs = getattr(next_lr_template, 'kwargs', {}).copy()

            # Apply overrides from the Jump data
            if isinstance(result.data, dict):
                next_kwargs.update(result.data)
            elif result.data is not None:
                # Assume single value maps to the first positional argument
                if next_args:
                    next_args[0] = result.data
                else:
                    next_args = [result.data]
            
            # Construct the new target, preserving the original jump selector binding
            current_target = LazyResult(
                task=next_lr_template.task,
                args=tuple(next_args),
                kwargs=next_kwargs,
                _jump_selector=getattr(next_lr_template, '_jump_selector', None)
            )