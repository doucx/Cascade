from typing import Dict, Any, List, Optional
from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef, ServiceDef
from cascade.foundation.ir.ops import Op, ComputeOp, ConstantOp

# A simple graph container for now
class ExecutionGraph:
    def __init__(self):
        self.ops: Dict[str, Op] = {}
        self.root_op_id: Optional[str] = None

    def add_op(self, op: Op):
        self.ops[op.id] = op


class Compiler:
    def __init__(self):
        self.graph = ExecutionGraph()
        # Memoization for structural sharing: Definition Fingerprint -> Op ID
        self._memo: Dict[str, str] = {}

    def compile(self, target_def: Definition) -> ExecutionGraph:
        """
        Main entry point. Compiles a Definition into an ExecutionGraph.
        """
        root_id = self._lower(target_def)
        self.graph.root_op_id = root_id
        return self.graph

    def _lower(self, definition: Definition) -> str:
        """
        Recursively lowers a Definition into an Op, returning the Op ID.
        """
        # TODO: integrate real fingerprinting in Phase 2
        # For now, we use object ID as a temporary placeholder for identity
        def_id = str(id(definition))
        
        if def_id in self._memo:
            return self._memo[def_id]

        op_id = None

        if isinstance(definition, TaskDef):
            op_id = self._lower_task(definition)
        # elif isinstance(definition, ServiceDef):
        #     op_id = self._lower_service(definition)
        else:
            raise NotImplementedError(f"Cannot compile definition type: {type(definition)}")

        self._memo[def_id] = op_id
        return op_id

    def _lower_task(self, task_def: TaskDef) -> str:
        # 1. Resolve Inputs
        inputs = {}
        
        for arg_name, arg_val in task_def.bindings.items():
            if isinstance(arg_val, Definition):
                # Recursively lower dependency
                inputs[arg_name] = self._lower(arg_val)
            else:
                # Literal -> ConstantOp
                # TODO: Use content hash for ID in next step
                const_id = f"const-{id(arg_val)}"
                if const_id not in self.graph.ops:
                    const_op = ConstantOp(id=const_id, value=arg_val)
                    self.graph.add_op(const_op)
                inputs[arg_name] = const_id

        # 2. Create ComputeOp
        # TODO: Use Fingerprint for ID
        op_id = f"op-{task_def.name}-{id(task_def)}"
        
        op = ComputeOp(
            id=op_id,
            inputs=inputs,
            callable_ref=f"{task_def.func.__module__}.{task_def.func.__qualname__}",
            config={
                "retry": task_def.retry_policy,
                "cache": task_def.cache_policy
            }
        )
        self.graph.add_op(op)
        return op_id