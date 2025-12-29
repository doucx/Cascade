简要回答
你的测试失败揭示了两个问题：一是代码库中残留了基于 `id()` 的非确定性 ID 生成逻辑（导致 `op-t-...` 格式的 ID）；二是 `IdentityService` 生成的指纹键名违反了 `Fingerprint` 类的严格命名公理（缺少一个段）。

我将重写 `builder.py` 以强制启用基于 SHA256 的确定性 ID 生成，并修复 `IdentityService.py` 中的键名以符合 `[State]_[Source]_[Object]_[Type]` 的四段式规范。

## [WIP] fix(compiler): enforce deterministic Op IDs and fix fingerprint schema

### 错误分析
1.  **非确定性 ID**: 测试失败显示 Op ID 为 `op-t-131...`，这是典型的 `f"op-{name}-{id(obj)}"` 格式。这说明 `Compiler` 在某些路径下使用了对象的内存地址作为 ID，而非基于内容的哈希。这违反了 Phase 2 的核心目标。
2.  **Schema 违规风险**: 代码审查发现 `IdentityService` 使用了 `baseline_config_hash`（3 段），而 `Fingerprint` 的正则 `^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$` 强制要求 4 段（State_Source_Object_Type）。这虽然可能未直接导致断言失败（取决于测试环境的指纹类版本），但必须修正以避免运行时崩溃。

### 用户需求
*   修复 `test_compiler_stable_identity` 和 `test_deterministic_identity` 的断言错误。
*   强制使用长哈希（SHA256 Hex）作为 Op ID。
*   确保 `Compiler` 的输出具有跨实例的确定性（Structural Sharing）。

### 目标
1.  重构 `cascade.compiler.builder.Compiler._lower_task`，确保它始终调用 `IdentityService.compute_op_id` 生成 SHA256 ID。
2.  修正 `cascade.foundation.identity.service.IdentityService`，使其生成的指纹键名符合 Axiom（将 `baseline_config_hash` 改为 `baseline_task_config_hash`）。

### 基本原理
通过消除对 Python 内置 `id()` 的依赖，改用基于代码签名（Module+Qualname）、配置（JSON Dump）和输入依赖（Recursive Hash）的 Merkle Tree 哈希策略，我们可以保证：
1.  **稳定性**: 同一代码在不同进程/机器生成的 ID 一致。
2.  **去重**: 相同的任务定义在图中只生成一个 Op 节点。
3.  **合规性**: 严格遵守架构定义的指纹命名规范。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #task/domain/compiler #task/object/identity #task/action/enforce

---

### Script

#### Acts 1: 修复 IdentityService 的键名 Schema

我们将 `baseline_config_hash` 修正为 `baseline_task_config_hash` 以满足 4 段式命名规范。

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/identity/service.py
~~~~~
~~~~~old
        fp = Fingerprint()
        fp["baseline_code_signature_hash"] = code_hash
        fp["baseline_config_hash"] = config_hash
        return fp

    @staticmethod
~~~~~
~~~~~new
        fp = Fingerprint()
        fp["baseline_code_signature_hash"] = code_hash
        fp["baseline_task_config_hash"] = config_hash
        return fp

    @staticmethod
~~~~~
~~~~~old
        # Mix code, config, and inputs
        seed = fingerprint["baseline_code_signature_hash"] + \
               fingerprint["baseline_config_hash"] + \
               input_hash
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
~~~~~
~~~~~new
        # Mix code, config, and inputs
        seed = fingerprint["baseline_code_signature_hash"] + \
               fingerprint["baseline_task_config_hash"] + \
               input_hash
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
~~~~~

#### Acts 2: 强制 Compiler 使用确定性 ID 生成逻辑

我们将重写 `builder.py`，确保没有任何回退到 `id()` 的逻辑，并正确处理 ConstantOp 的哈希。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
- 运行测试 `pytest packages/cascade-compiler/tests/` 验证修复是否生效。
- 考虑在 `IdentityService` 中添加更健壮的输入校验，确保所有传入的哈希值都是有效的 SHA256 字符串。
