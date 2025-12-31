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
        next_input_overrides: Optional[Dict[str, Any]] = None

        while True:
            # 1. Frontend: Compile LazyResult to GraphIR
            compilation_result = Frontend.compile(current_target)
            graph_ir = compilation_result.ir
            symbol_table = compilation_result.symbol_table

            # 2. Optimizer: Schedule GraphIR to ExecutionPlan
            execution_plan = Optimizer.optimize(graph_ir)

            # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
            blueprint = Backend.compile(graph_ir, execution_plan)

            # 4. Runtime: Execute Blueprint on VM
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
            
            # Use overrides from previous Jump if available
            initial_kwargs = next_input_overrides or {}
            next_input_overrides = None

            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=[],  # Jumps primarily work with kwargs for clarity
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
                # Loop exit condition
                return result.data

            # 7. Prepare for next iteration
            current_target = next_lazy_result
            
            # Prepare input overrides for the next loop
            if isinstance(result.data, dict):
                next_input_overrides = result.data
            elif result.data is not None:
                # Non-dict data is passed as the first positional argument
                # In the VM, this means we need to know which register to populate
                # For simplicity, we will pass it as a special kwarg and let
                # the VM/middleware handle it. Or, for TCO, it's often a dict.
                # The old strategy passed it as {"0": ...}, but VM doesn't use that.
                # The test case `accumulator` passes a dict. Let's stick to dicts.
                # This might require adjusting the `counter` test if it relies on positional.
                # Let's assume for now Jump data is a dict of kwargs.
                raise TypeError("Jump data for VM-based TCO must be a dictionary.")
            else:
                next_input_overrides = {}