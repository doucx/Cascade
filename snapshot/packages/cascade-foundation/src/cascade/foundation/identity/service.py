import hashlib
import json
from typing import Any
from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef
from cascade.foundation.identity.fingerprint import Fingerprint

class IdentityService:
    def compute_fingerprint(self, definition: Definition) -> Fingerprint:
        if isinstance(definition, TaskDef):
            return self._compute_task_fingerprint(definition)
        raise NotImplementedError(f"Cannot fingerprint {type(definition)}")

    def _compute_task_fingerprint(self, task_def: TaskDef) -> Fingerprint:
        # 1. Code Identity (Simplistic: module + qualname)
        # In a real impl, this would hash the bytecode or source AST.
        code_id = f"{task_def.func.__module__}:{task_def.func.__qualname__}"
        code_hash = hashlib.sha256(code_id.encode("utf-8")).hexdigest()
        
        # 2. Config Identity (Name, Policies)
        # We assume policies are JSON-serializable dicts or None
        config_data = {
            "name": task_def.name,
            "retry": task_def.retry_policy,
            "cache": task_def.cache_policy
        }
        config_str = json.dumps(config_data, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()
        
        # 3. Structure Identity (Bindings)
        # This is computed by the Compiler.
        
        fp = Fingerprint()
        fp["baseline_code_signature_hash"] = code_hash
        # FIX: Conforming to 4-segment naming axiom
        fp["baseline_task_config_hash"] = config_hash
        return fp

    @staticmethod
    def compute_op_id(fingerprint: Fingerprint, input_hash: str) -> str:
        """
        Combines the Definition's static fingerprint with the resolved inputs' hash
        to form the final Execution Op ID.
        """
        # Mix code, config, and inputs
        seed = fingerprint["baseline_code_signature_hash"] + \
               fingerprint["baseline_task_config_hash"] + \
               input_hash
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()