from typing import Dict, Any, List, Optional
import hashlib
import json

from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef, ServiceDef
from cascade.foundation.ir.ops import Op, ComputeOp, ConstantOp
from cascade.foundation.identity.service import IdentityService

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
        self.identity_service = IdentityService()
        # Memoization for structural sharing: Definition Object ID -> Op ID
        # Note: We use object ID for memoization during a single compile pass
        # to handle DAG diamonds/cycles, but the produced Op IDs are deterministic.
        self._memo: Dict[int, str] = {}

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
        # Use object ID only for cycle detection/memoization within this run
        obj_id = id(definition)
        
        if obj_id in self._memo:
            return self._memo[obj_id]

        op_id = None

        if isinstance(definition, TaskDef):
            op_id = self._lower_task(definition)
        # elif isinstance(definition, ServiceDef):
        #     op_id = self._lower_service(definition)
        else:
            raise NotImplementedError(f"Cannot compile definition type: {type(definition)}")

        self._memo[obj_id] = op_id
        return op_id

    def _lower_task(self, task_def: TaskDef) -> str:
        # 1. Resolve Inputs and calculate Input Hash
        inputs = {}
        input_hash_parts = []
        
        # Sort keys for deterministic hashing
        for arg_name in sorted(task_def.bindings.keys()):
            arg_val = task_def.bindings[arg_name]
            
            if isinstance(arg_val, Definition):
                # Recursively lower dependency
                upstream_op_id = self._lower(arg_val)
                inputs[arg_name] = upstream_op_id
                input_hash_parts.append(f"{arg_name}:{upstream_op_id}")
            else:
                # Literal -> ConstantOp
                # Calculate stable hash for literal
                lit_hash = hashlib.sha256(repr(arg_val).encode("utf-8")).hexdigest()
                const_id = f"const-{lit_hash}"
                
                if const_id not in self.graph.ops:
                    const_op = ConstantOp(id=const_id, value=arg_val)
                    self.graph.add_op(const_op)
                
                inputs[arg_name] = const_id
                input_hash_parts.append(f"{arg_name}:{const_id}")

        input_hash = hashlib.sha256("|".join(input_hash_parts).encode("utf-8")).hexdigest()

        # 2. Calculate Static Fingerprint
        static_fp = self.identity_service.compute_fingerprint(task_def)
        task_def.fingerprint = static_fp # Store it back

        # 3. Generate Final Op ID
        op_id = IdentityService.compute_op_id(static_fp, input_hash)
        
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