## [WIP] fix: Remove Legacy ID Usage in Test

### 错误分析
测试失败 `assert 'op-t-124313387834768' == 'op-t-124313387824496'` 暴露出 `test_dependency_linking.py` 中的 `test_deterministic_identity` 断言失败。
这表明 Compiler **仍然在使用 Python 对象 ID (`id(task_def)`)** 来生成 `op_id`，而不是我们刚刚实现的 `IdentityService` 逻辑。

仔细检查上一步的 `patch_file` 操作，我发现我们在 Acts 3 中更新了 `_lower` 和 `_lower_task`，但我遗漏了一个关键点：
我更新了 `builder.py` 的代码逻辑，但我没有移除之前在 `_lower_task` 末尾的旧代码或者我可能在 patch 时出错了。让我们检查一下 `builder.py` 的实际状态。

根据报错信息 `op-t-124313387824496`，这显然还是 `f"op-{task_def.name}-{id(task_def)}"` 的格式。说明我之前的 patch 没有正确覆盖到这一行，或者我保留了旧的 ID 生成逻辑作为 fallback。

### 用户需求
修复 Compiler，使其在生成 Op ID 时**绝对不要**使用 `id()`，而是使用 `IdentityService.compute_op_id`。

### 评论
这是 TDD 的价值所在。测试通过红色状态告诉我们重构未完成。

### 目标
彻底替换 `builder.py` 中的 `_lower_task` 方法，确保只使用指纹。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/compiler #scope/core
#ai/instruct
#task/domain/core #task/object/compiler #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 强制重写 Compiler 的 _lower_task 方法
我将整个重写 `_lower_task` 方法，确保没有残留的 `id()` 逻辑。

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

#### Acts 2: 更新测试用例
由于我们改变了 Op ID 的格式（从 `op-name-id` 变成了 `sha256`），之前的测试断言可能需要更新。
检查 `test_builder.py` 中的断言。
`test_compiler_lowering_basic_task` 没有断言 ID 格式，只断言了结构，所以应该没问题。
`test_dependency_linking.py` 中的 `test_deterministic_identity` 正是我们想要的。

但是，`test_builder.py` 中被注释掉的断言：
```python
    # Note: In Phase 2 start, we might still be using id(), so this test expects FAIL 
    # until we implement real fingerprinting. 
    # But for TDD, we write the expectation now.
    # assert g1.root_op_id == g2.root_op_id 
```
现在我们已经实现了指纹，是时候启用这个测试了。

~~~~~act
patch_file
packages/cascade-compiler/tests/test_builder.py
~~~~~
~~~~~python.old
    # Note: In Phase 2 start, we might still be using id(), so this test expects FAIL 
    # until we implement real fingerprinting. 
    # But for TDD, we write the expectation now.
    # assert g1.root_op_id == g2.root_op_id 
    pass
~~~~~
~~~~~python.new
    # Now that we have fingerprinting, this must pass
    assert g1.root_op_id == g2.root_op_id
~~~~~

### 下一步建议
再次运行测试。现在 `test_dependency_linking.py` 和 `test_builder.py` 都应该通过。
