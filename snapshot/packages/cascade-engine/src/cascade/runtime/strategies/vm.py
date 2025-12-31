import asyncio
from contextlib import ExitStack
from typing import Any, Dict

from cascade.spec.protocols import StateBackend
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager

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
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        # Returns CompilationResult(ir, symbol_table)
        compilation_result = Frontend.compile(target)
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
        # Outer -> Inner
        vm.set_middlewares([
            # 1. Arguments must be resolved first so others see values (e.g. dynamic constraints?)
            # Actually, standard is: Retry -> Resource -> Execute.
            # Argument Resolution usually happens right before Core execution?
            # Or at the very beginning so Retry sees resolved args? 
            # Args might contain resources which need to be acquired? 
            # No, ResourceOperand just looks up an ALREADY active resource.
            # Resource acquisition (Lifecycle) is for compute resources (CPU/GPU) claimed by the task metadata.
            
            RetryMiddleware(),
            ResourceLifecycleMiddleware(self.resource_manager),
            ConstraintMiddleware(self.constraint_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])

        if isinstance(target, MappedLazyResult):
            initial_args = []
            initial_kwargs = dict(target.mapping_kwargs)
        else:
            initial_args = list(target.args)
            initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(
            blueprint,
            symbol_table=symbol_table,
            initial_args=initial_args,
            initial_kwargs=initial_kwargs,
        )