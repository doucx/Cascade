太棒了，**Green Light**。

现在我们有了一个能跑通的骨架：
1.  **Identity**: `Fingerprint` 逻辑已验证。
2.  **IR**: `TaskDef` 和 `Op` ADT 结构已稳定（解决了继承问题）。
3.  **Compiler**: 能够将最简单的 `TaskDef`（含 Literal 参数）降级为 `ComputeOp` + `ConstantOp`。

接下来是 **Phase 2 - TDD Cycle 3 (Linking)** 和 **Fingerprint Integration**。我们需要让 Compiler 真正利用 Fingerprint 来生成 Op ID，而不是依赖 Python 的 `id()`，并且要处理 `Definition` 之间的依赖关系（Dependency Linking）。

## [WIP] feat: Implement Fingerprint-Based Identity & Dependency Linking

### 用户需求
1.  **集成 Fingerprint**: 在 Compiler 中集成 `Fingerprint` 计算逻辑，确保 Op ID 是内容寻址的（Content-Addressable）。
2.  **实现依赖链接**: 让 Compiler 能够处理 `TaskDef` 之间的依赖关系（即一个 Task 的输出作为另一个 Task 的输入），并生成正确的 Edge。

### 评论
这是 V2 架构 "Compiler-First" 的核心体现。
*   **确定性**: 相同的定义 + 相同的环境 = 相同的 Fingerprint = 相同的 Op ID。这意味着如果代码没变，图的 ID 就不变，缓存自动生效。
*   **静态链接**: Compiler 必须能够在不运行代码的情况下，递归地解析整个 DAG，将 Python 对象引用的图转换为 Op ID引用的图。

### 目标
1.  创建 `IdentityService`，负责计算 Definition 的 Fingerprint。
2.  更新 `TaskDef` 的 lowering 逻辑，使用 Fingerprint 作为 Op ID。
3.  更新 `Compiler`，使其支持递归降级依赖项。
4.  编写测试验证上述两点。

### 基本原理
*   **Fingerprint Axiom**: `TaskDef` 的指纹 = `hash(code_body_hash + config_hash + inputs_fingerprints)`.
*   **Inputs Fingerprints**: 这意味着必须先计算上游依赖的 Fingerprint，才能计算当前节点的 Fingerprint（Post-order Traversal）。

### 标签
#intent/build #flow/ready #priority/high
#comp/compiler #comp/foundation
#ai/instruct
#task/domain/core #task/object/compiler #task/action/implement
#task/state/continue #task/status/active

---

### Script

#### Acts 1: [RED] TDD Cycle 3 - 依赖链接与指纹
编写一个新的测试，验证 Compiler 能否处理依赖链，并且生成的 ID 是稳定的（非 `id()` 依赖）。

~~~~~act
write_file
packages/cascade-compiler/tests/test_dependency_linking.py
~~~~~
~~~~~python
import pytest
from cascade.foundation.definitions.model import TaskDef
from cascade.foundation.ir.ops import ComputeOp
from cascade.compiler.builder import Compiler

def func_a(x): return x
def func_b(y): return y + 1

def test_dependency_chain_lowering():
    # Construct: Task B -> Task A -> Literal
    
    # Task A depends on literal 10
    task_a = TaskDef(
        name="task_a",
        func=func_a,
        bindings={"x": 10}
    )
    
    # Task B depends on Task A
    task_b = TaskDef(
        name="task_b",
        func=func_b,
        bindings={"y": task_a}
    )
    
    compiler = Compiler()
    graph = compiler.compile(task_b)
    
    # 1. Check Root (Task B)
    root_op = graph.ops[graph.root_op_id]
    assert isinstance(root_op, ComputeOp)
    assert root_op.callable_ref.endswith("func_b")
    
    # 2. Check Dependency Link
    # root_op.inputs["y"] should be the ID of Task A's op
    op_a_id = root_op.inputs["y"]
    assert op_a_id in graph.ops
    op_a = graph.ops[op_a_id]
    
    assert isinstance(op_a, ComputeOp)
    assert op_a.callable_ref.endswith("func_a")
    
    # 3. Check Task A's input
    # op_a.inputs["x"] should be a ConstantOp
    const_id = op_a.inputs["x"]
    assert graph.ops[const_id].value == 10

def test_deterministic_identity():
    # Two separate compiler instances processing identical definitions
    # MUST produce identical Op IDs.
    
    t1 = TaskDef(name="t", func=func_a, bindings={"x": 1})
    c1 = Compiler()
    g1 = c1.compile(t1)
    
    t2 = TaskDef(name="t", func=func_a, bindings={"x": 1})
    c2 = Compiler()
    g2 = c2.compile(t2)
    
    assert g1.root_op_id == g2.root_op_id
    assert g1.root_op_id is not None
    # Ensure it's not using python object id (which would likely be numeric strings)
    # Fingerprint hashes are usually hex strings
    assert not g1.root_op_id.isdigit() 
~~~~~

#### Acts 2: 实现 IdentityService (Stub)
在 `cascade-foundation` 中创建一个简单的指纹计算服务。为了不引入复杂的代码分析库，我们先基于函数名和模块名做哈希（足以通过测试）。

~~~~~act
write_file
packages/cascade-foundation/src/cascade/foundation/identity/service.py
~~~~~
~~~~~python
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
        # Note: This is computed by the Compiler usually, because it involves
        # resolving dependencies recursively. 
        # However, IdentityService defines the *rule* for the hash.
        # For now, we return a partial fingerprint, the Compiler will augment it
        # with input hashes to form the final Op ID.
        
        fp = Fingerprint()
        fp["baseline_code_signature_hash"] = code_hash
        fp["baseline_config_hash"] = config_hash
        return fp

    @staticmethod
    def compute_op_id(fingerprint: Fingerprint, input_hash: str) -> str:
        """
        Combines the Definition's static fingerprint with the resolved inputs' hash
        to form the final Execution Op ID.
        """
        # Mix code, config, and inputs
        seed = fingerprint["baseline_code_signature_hash"] + \
               fingerprint["baseline_config_hash"] + \
               input_hash
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
~~~~~

#### Acts 3: [GREEN] 集成到 Compiler
修改 `Compiler`，引入 `IdentityService`，并使用它来生成确定的 Op ID。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python.old
from typing import Dict, Any, List, Optional
from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef, ServiceDef
from cascade.foundation.ir.ops import Op, ComputeOp, ConstantOp

# A simple graph container for now
class ExecutionGraph:
~~~~~
~~~~~python.new
from typing import Dict, Any, List, Optional
import hashlib
import json

from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef, ServiceDef
from cascade.foundation.ir.ops import Op, ComputeOp, ConstantOp
from cascade.foundation.identity.service import IdentityService

# A simple graph container for now
class ExecutionGraph:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python.old
class Compiler:
    def __init__(self):
        self.graph = ExecutionGraph()
        # Memoization for structural sharing: Definition Fingerprint -> Op ID
        self._memo: Dict[str, str] = {}

    def compile(self, target_def: Definition) -> ExecutionGraph:
~~~~~
~~~~~python.new
class Compiler:
    def __init__(self):
        self.graph = ExecutionGraph()
        self.identity_service = IdentityService()
        # Memoization for structural sharing: Definition Object ID -> Op ID
        # Note: We use object ID for memoization during a single compile pass
        # to handle DAG diamonds/cycles, but the produced Op IDs are deterministic.
        self._memo: Dict[int, str] = {}

    def compile(self, target_def: Definition) -> ExecutionGraph:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
运行测试。`test_deterministic_identity` 应该会通过，因为我们不再使用 `id()`，而是使用内容哈希。这将证明我们的 Compiler 真正实现了 Content-Addressable Identity。
