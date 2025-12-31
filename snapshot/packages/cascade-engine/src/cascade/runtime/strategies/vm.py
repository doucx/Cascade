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

        # 4. Linking Phase: Resolve function pointers
        for instr in blueprint.instructions:
            if isinstance(instr, (Call, MapCall)):
                if instr.structure_hash not in symbol_table:
                    raise RuntimeError(
                        f"Linking failed: structure_hash '{instr.structure_hash}' "
                        f"for task '{instr.task_name}' not found in symbol table."
                    )
                instr.func = symbol_table[instr.structure_hash]

        # 5. Runtime: Execute Blueprint on VM
        # Note: The new VM doesn't yet support ResourceManager/ConstraintManager injection
        # directly in the same way. For Phase 5 initial integration, we instantiate the
        # pure VM. Future tasks will reintegrate resource management.
        vm = VirtualMachine()
        
        # Prepare initial arguments
        # The new VM expects 'initial_kwargs' mapping directly to registers if needed,
        # or it relies on the blueprint's structure.
        
        if isinstance(target, MappedLazyResult):
            initial_args = []
            initial_kwargs = dict(target.mapping_kwargs)
        else:
            initial_args = list(target.args)
            initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)