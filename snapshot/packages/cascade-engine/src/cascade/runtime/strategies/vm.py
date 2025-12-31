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

        if isinstance(current_target, MappedLazyResult):
            next_initial_args = []
            next_initial_kwargs = dict(current_target.mapping_kwargs)
        else:
            next_initial_args = list(current_target.args)
            next_initial_kwargs = dict(current_target.kwargs)

        # Trampoline loop for Tail Call Optimization (TCO) via Jump signals
        while True:
            # 1. Frontend: Compile LazyResult to GraphIR
            # Returns CompilationResult(ir, symbol_table)
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

            # Configure Middleware Pipeline (Order matters!)
            vm.set_middlewares(
                [
                    ObservabilityMiddleware(self.bus, run_id),
                    RetryMiddleware(),
                    ConstraintMiddleware(self.constraint_manager),
                    ResourceLifecycleMiddleware(self.resource_manager),
                    ArgumentResolutionMiddleware(active_resources, params or {}),
                ]
            )

            vm_result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=next_initial_args,
                initial_kwargs=next_initial_kwargs,
            )

            # 6. Check for Jump signal
            if not isinstance(vm_result, Jump):
                return vm_result  # Normal termination

            # --- Handle Jump ---
            # This logic is ported from the old GraphExecutionStrategy
            jump_selector = getattr(current_target, '_jump_selector', None)
            if not jump_selector:
                raise RuntimeError(
                    "Task returned a Jump signal but no jump selector was bound."
                )

            next_target = jump_selector.routes.get(vm_result.target_key)
            if next_target is None:
                # Loop exit condition
                return vm_result.data

            # Prepare for next iteration
            current_target = next_target

            # Convert jump data to args/kwargs for the next VM execution
            data = vm_result.data
            if isinstance(data, dict):
                next_initial_args = []
                next_initial_kwargs = data
            elif isinstance(data, (list, tuple)):
                next_initial_args = list(data)
                next_initial_kwargs = {}
            else:
                next_initial_args = [data] if data is not None else []
                next_initial_kwargs = {}