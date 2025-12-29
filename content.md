## [WIP] architect: Cascade V2 Phase 1 - IR Ops & Compiler Skeleton

### 错误分析
在 Phase 0 中，我们使用了 `cascade-core` 作为包名以及 `cascade.core` 作为 Python 模块名。这违反了“绝对禁止使用 core 作为包命名”的后续约束。为了保证架构的洁净和避免未来的命名冲突，Phase 1 必须首先执行一次迁移重构，将 `core` 命名空间更正为 `foundation`。

### 用户需求
1.  **定义底层 Op ADT**: 创建 `ComputeOp`, `ResourceOp` 等严格数据结构，作为运行时的指令集。
2.  **编写 Compiler 骨架**: 实现将 `TaskDef` 转换为 `Op Graph` 的初步逻辑。
3.  **修正命名**: 确保不使用 `core` 命名。

### 评论
将 `Definition` (Level 0 IR) 与 `Op` (Level 1 IR) 分离是 "Compiler-First" 架构的核心。`Op` 层将完全消除 `Optional` 的不确定性，成为 Engine 可直接执行的静态指令。同时，`Compiler` 将承担起“翻译官”的角色，负责将用户友好的 `Definition` 降级为机器友好的 `Op`。

### 目标
1.  将 `packages/cascade-core` 迁移至 `packages/cascade-foundation`，并将 python 模块 `cascade.core` 重构为 `cascade.foundation`。
2.  在 `cascade.foundation.ir.ops` 中定义 `Op` 及其子类。
3.  创建 `packages/cascade-compiler` 包。
4.  实现基础的 `Compiler` 类和 `lowering` 逻辑。

### 基本原理
*   **迁移**: 立即修正是成本最低的重构方式。`foundation` 语义准确，代表了 IR 和 Identity 是上层组件的基础。
*   **Op ADT**: 采用 `@dataclass` 和继承结构来定义 Op，利用 Python 的类型提示来强制结构完整性。所有的 Op 必须有唯一的 ID (Fingerprint) 和明确的输入/控制依赖槽位。
*   **Compiler**: 编译器不仅是转换器，也是验证器。它在构建图的过程中就能发现参数缺失等错误，而不是等到运行时。

### 标签
#intent/architect #intent/refine #flow/draft #priority/high
#comp/foundation #comp/compiler #scope/core
#ai/instruct
#task/domain/core #task/object/ir #task/action/implement
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 命名空间迁移 (Core -> Foundation)
将 Phase 0 创建的 `cascade-core` 包重命名为 `cascade-foundation`，并更新相关文件路径和引用。

~~~~~act
move_file
packages/cascade-core
packages/cascade-foundation
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-foundation/src/cascade/core packages/cascade-foundation/src/cascade/foundation
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/pyproject.toml
~~~~~
~~~~~toml.old
[project]
name = "cascade-core"
version = "2.0.0-alpha"
description = "Core IR and Identity system for Cascade V2"
~~~~~
~~~~~toml.new
[project]
name = "cascade-foundation"
version = "2.0.0-alpha"
description = "Foundation IR and Identity system for Cascade V2"
~~~~~

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/base.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from cascade.core.identity.fingerprint import Fingerprint
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from cascade.foundation.identity.fingerprint import Fingerprint
~~~~~

#### Acts 2: 定义 Op ADT (Level 1 IR)
创建 `cascade.foundation.ir.ops` 模块，定义运行时指令集。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-foundation/src/cascade/foundation/ir
touch packages/cascade-foundation/src/cascade/foundation/ir/__init__.py
~~~~~

~~~~~act
write_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class Op:
    """
    Base class for Level 1 IR Operations.
    Ops are the executable instructions for the Engine.
    They must be strict, fully resolved, and immutable.
    """
    # The structural hash/fingerprint of this operation.
    # Serves as the primary key for caching and identification.
    id: str

    # Data dependencies: Map[ArgName, UpstreamOpID]
    # Represents the flow of data from upstream ops to this op's arguments.
    inputs: Dict[str, str] = field(default_factory=dict)

    # Control dependencies: List[UpstreamOpID]
    # Represents explicit execution ordering (e.g. "run after X").
    control_deps: List[str] = field(default_factory=list)


@dataclass
class ComputeOp(Op):
    """
    Represents a computational task (function execution).
    """
    # Fully qualified name of the callable (e.g. "my_module.my_func")
    callable_ref: str
    
    # Static configuration (timeouts, retry policies, etc.)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstantOp(Op):
    """
    Represents a static value.
    Used for literal arguments.
    """
    value: Any


@dataclass
class ResourceOp(Op):
    """
    Represents a resource lifecycle action.
    The Engine handles the actual acquisition/release logic.
    """
    resource_name: str
    action: str  # "acquire" or "release"


@dataclass
class MultiplexOp(Op):
    """
    Represents a branching decision (Router).
    The 'selector' input determines which branch key to activate.
    """
    # Map[BranchKey, DownstreamOpID]
    # Note: This describes valid forward paths, but actual execution flow
    # is determined by the selector value at runtime.
    branches: Dict[str, str] = field(default_factory=dict)
~~~~~

#### Acts 3: 初始化 cascade-compiler 包
创建编译器包的基础结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-compiler/src/cascade/compiler
touch packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~

~~~~~act
write_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-compiler"
version = "2.0.0-alpha"
description = "Static Compiler for Cascade V2"
dependencies = [
    "cascade-foundation",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 4: 实现 Compiler 骨架
创建 `builder.py`，实现将 Definition 转换为 Op 的基础逻辑。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python
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
        # 1. Resolve Inputs (Recursively lower dependencies)
        # Note: This is a skeleton. Real implementation needs to inspect
        # task_def bindings (which we haven't fully defined in Phase 0 model yet).
        inputs = {}
        
        # Mocking input resolution for now
        # for arg_name, arg_val in task_def.bindings.items():
        #     if isinstance(arg_val, Definition):
        #         inputs[arg_name] = self._lower(arg_val)
        #     else:
        #         # Literal -> ConstantOp
        #         const_op = ConstantOp(id=f"const-{id(arg_val)}", value=arg_val)
        #         self.graph.add_op(const_op)
        #         inputs[arg_name] = const_op.id

        # 2. Create ComputeOp
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

### 下一步建议
1.  **Phase 2**: 完善 `Compiler` 逻辑。
    *   实现 `Static Argument Resolver`：在 `TaskDef` 中添加 `bindings` 字段，并在 Compiler 中实现对 Literal 和 Dependency 的解析逻辑。
    *   集成 `Fingerprint`：在 `_lower` 过程中真正计算并使用 Fingerprint 作为 Op ID，实现基于内容的寻址。
2.  **Phase 2 Extension**: 处理 `ServiceDef` 的 lowering 逻辑（例如将 SQL 配置转换为 ComputeOp）。
