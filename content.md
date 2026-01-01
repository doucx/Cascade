好的，我们已经有了明确的诊断和经过批准的战略。现在开始执行修复计划的第一步：**重构编译器 IR (`TaskDef`)**，使其携带明确的、符合新公理的链接身份。

这将从根本上解决信息丢失的问题，为后续所有修复工作奠定坚实的基础。

## [WIP] refactor(compiler): Refactor TaskDef IR to use explicit canonical hash

### 用户需求
根据新的 v3.0 哈希公理，重构编译器的核心中间表示（IR）`TaskDef`。必须移除模糊的 `fingerprint` 字段，并引入一个明确的、用于链接的 `canonical_code_structure_hash` 字段。

### 评论
这是解决“身份危机”的根本性举措。通过将链接身份（`canonical_code_structure_hash`）提升为 IR 的一等公民，我们为编译器链（Frontend -> Backend -> Executor）建立了清晰、无歧义的契约。此举将 `Fingerprint` 的职责严格限定在“状态管理”领域，使编译器 IR 更加纯粹和健壮，彻底杜绝了因身份混淆导致的链接失败。

### 目标
1.  **修改 `cascade.spec.ir.models.TaskDef`**: 移除 `fingerprint` 字段，添加 `canonical_code_structure_hash` 字段。
2.  **更新 `cascade.compiler.analysis.reflection.ReflectionAnalyzer`**: 修改其逻辑，使其计算并填充新的 `canonical_code_structure_hash` 字段，而不是创建 `Fingerprint` 对象。
3.  **更新 IR 消费者**: 修改 `Frontend` 和 `HashingService` 中所有访问 `TaskDef.fingerprint` 的代码，使其改为访问新的 `TaskDef.canonical_code_structure_hash` 字段。

### 基本原理
我们正在执行“重铸公理，定义哈希系统”战略的第二步。`TaskDef` 是连接静态分析（Frontend）和拓扑构建（Backend）的关键数据结构。通过在这个结构中强制实施明确的身份契约，我们确保了链接所需的 `canonical` 哈希信息能够无损地在编译器各阶段之间传递，从而从源头上解决了 `PhysicsExecutor` 的链接失败问题。

### 标签
#intent/refine #flow/ready #priority/critical #comp/compiler #comp/spec #scope/core #ai/instruct #task/domain/testing #task/object/compiler-ir #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `TaskDef` IR 规范

首先，我们修改核心 IR 定义 `TaskDef`，使其符合新的架构公理。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.policy import ExecutionPolicy


class EdgeKind(str, Enum):
~~~~~
~~~~~python.new
from cascade.spec.policy import ExecutionPolicy


class EdgeKind(str, Enum):
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable, linkable identity of this task definition.
    # This hash is computed from the static code structure and serves as
    # the key for the symbol_table.
    canonical_code_structure_hash: str
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~

#### Acts 2: 更新 `ReflectionAnalyzer` 以生成新的 IR

接下来，修改 `ReflectionAnalyzer` 以计算并填充新的 `canonical_code_structure_hash` 字段。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/analysis/reflection.py
~~~~~
~~~~~python.old
import inspect
import hashlib
from typing import Any, List, Optional

from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from .protocols import TaskAnalyzer

# Type hint for the Cascade Task wrapper
~~~~~
~~~~~python.new
import inspect
import hashlib
from typing import Any, List, Optional

from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from .protocols import TaskAnalyzer

# Type hint for the Cascade Task wrapper
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/analysis/reflection.py
~~~~~
~~~~~python.old
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )
~~~~~
~~~~~python.new
        # 3. Compute canonical hash for linking
        # This hash represents the stable, structural identity of the code.
        canonical_code_structure_hash = self._compute_canonical_code_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        return TaskDef(
            name=name,
            args=args,
            canonical_code_structure_hash=canonical_code_structure_hash,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/analysis/reflection.py
~~~~~
~~~~~python.old
        return args

    def _compute_structure_hash(
        self,
        name: str,
        args: List[ArgumentDef],
~~~~~
~~~~~python.new
        return args

    def _compute_canonical_code_structure_hash(
        self,
        name: str,
        args: List[ArgumentDef],
~~~~~

#### Acts 3: 更新 `Frontend` 和 `HashingService` 的 IR 消费逻辑

最后，更新所有消费 `TaskDef` 的地方，使其使用新的字段。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        task_def = self.analyzer.analyze(obj.task)

        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]
        self.symbol_table[code_hash] = obj.task.func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
~~~~~
~~~~~python.new
        task_def = self.analyzer.analyze(obj.task)

        # Populate Symbol Table using the canonical hash as the link key
        self.symbol_table[task_def.canonical_code_structure_hash] = obj.task.func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        task_def = self.analyzer.analyze(obj.factory)

        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]

        # Ensure we store the raw function, not the Task wrapper
        # The analyzer usually handles extraction, but we need the raw callable for VM
~~~~~
~~~~~python.new
        task_def = self.analyzer.analyze(obj.factory)

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = func

        # Ensure we store the raw function, not the Task wrapper
        # The analyzer usually handles extraction, but we need the raw callable for VM
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~
~~~~~python.old
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
~~~~~
~~~~~python.new
    ) -> str:
        # 1. Start with the stable, canonical hash of the code structure
        canonical_code_structure_hash = definition.canonical_code_structure_hash
        components = [f"CanonicalCodeStructureHash:{canonical_code_structure_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~
~~~~~python.old
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
~~~~~
~~~~~python.new
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CanonicalCodeStructureHash({node.definition.canonical_code_structure_hash})"
        )

        if node.retry_policy:
            rp = node.retry_policy
~~~~~

### 下一步建议
我们已经成功地将“链接身份”注入了编译器的前端和中间表示。

下一步是**第三步：修正编译器链的后端**。我们需要：
1.  **修改 `cascade.spec.topology.PhysicsFuncNode`**: 为其添加 `canonical_code_structure_hash` 字段。
2.  **修改 `cascade.compiler.backend`**: 确保它在将 `NodeIR` 转换为 `PhysicsFuncNode` 时，无损地传递这个新的哈希字段。
3.  **修改 `cascade.vm.executors.physics.PhysicsExecutor`**: 让它使用这个新字段进行正确的 `symbol_table` 查找。

这将完成整个编译器链的身份传递闭环。
