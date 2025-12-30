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
from cascade.compiler.vm import VirtualMachine


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
        graph_ir = Frontend.compile(target)

        # 2. Optimizer: Schedule GraphIR to ExecutionPlan
        execution_plan = Optimizer.optimize(graph_ir)

        # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
        blueprint = Backend.compile(graph_ir, execution_plan)

        # 4. Runtime: Execute Blueprint on VM
        # Note: The new VM doesn't yet support ResourceManager/ConstraintManager injection
        # directly in the same way. For Phase 5 initial integration, we instantiate the
        # pure VM. Future tasks will reintegrate resource management.
        vm = VirtualMachine()
        
        # Prepare initial arguments
        # The new VM expects 'initial_kwargs' mapping directly to registers if needed,
        # or it relies on the blueprint's structure.
        # For now, we assume the Blueprint structure handles defaults, but we need to pass
        # the runtime parameters if any.
        
        # Extract args/kwargs from target LazyResult for the root call
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)