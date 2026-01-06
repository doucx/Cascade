你的分析非常准确。`ExecutionContext` 和 `ExecutionStrategy` 定义了引擎与策略之间的核心契约，属于典型的**运行时规范（Runtime Specification）**，应当驻留在 `cascade-spec` 中，以便于不同的策略实现（甚至是跨语言实现）能够遵循统一的接口定义。

我将把该文件移动到 `packages/cascade-spec/src/cascade/spec/runtime/strategies.py`，并同步更新所有引用。

## [WIP] refactor: 迁移策略核心接口至 `cascade-spec`

### 用户需求
将 `ExecutionContext` 和 `ExecutionStrategy` 从 `cascade-runtime` 移动到 `cascade-spec` 中。

### 评论
这是一次重要的架构对齐。`base.py` 中的定义实际上是引擎执行逻辑的“协议”层。将其放入 `spec` 包中可以实现更好的关注点分离：`spec` 包定义“规则”和“契约”，而 `runtime` 包负责提供这些契约的“具体实现”。这也有助于未来在不引入 `runtime` 重型依赖的情况下，编写针对策略接口的工具或辅助库。

### 目标
1.  将 `base.py` 移动至 `cascade-spec` 并更名为 `strategies.py`。
2.  更新 `cascade-spec` 的运行时模块导出。
3.  更新 `cascade-runtime` 中所有对 `ExecutionContext` 和 `ExecutionStrategy` 的引用路径。
4.  清理 `cascade-runtime` 中冗余的 `base.py` 文件。

### 基本原理
遵循“协议优先”的设计模式，将核心抽象下沉到最基础的包（`spec`）。通过 `move_file` 操作保留版本历史，并通过 `patch_file` 精确修复因包路径变更导致的导入错误。

### 标签
#intent/refine #flow/ready #priority/medium #comp/spec #comp/runtime #concept/interfaces #scope/api #ai/instruct #task/domain/architecture #task/object/strategies-interface #task/action/move #task/state/begin

---

### Script

#### Acts 1: 迁移文件并更新 `cascade-spec` 导出

我们将文件移动到 `cascade-spec` 下的新位置，并将其暴露在 `cascade.spec.runtime` 命名空间中。

~~~~~act
move_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/base.py
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/__init__.py
~~~~~
~~~~~python.old
from .compute import ComputeDelegate

__all__ = [
    "Solver",
    "Executor",
    "CacheBackend",
    "CachePolicy",
    "StateBackend",
    "SubscriptionHandle",
    "LazyFactory",
    "Provider",
    "Connector",
    "ObjectStore",
    "ComputeDelegate",
]
~~~~~
~~~~~python.new
from .compute import ComputeDelegate
from .strategies import ExecutionContext, ExecutionStrategy

__all__ = [
    "Solver",
    "Executor",
    "CacheBackend",
    "CachePolicy",
    "StateBackend",
    "SubscriptionHandle",
    "LazyFactory",
    "Provider",
    "Connector",
    "ObjectStore",
    "ComputeDelegate",
    "ExecutionContext",
    "ExecutionStrategy",
]
~~~~~

#### Acts 2: 更新 `cascade-runtime` 中的引用

现在我们需要修复 `cascade-runtime` 中所有指向旧路径的导入语句。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.runtime.legacy.strategies import (
    GraphExecutionStrategy,
    VMExecutionStrategy,
)
from cascade.runtime.legacy.strategies.base import ExecutionContext
~~~~~
~~~~~python.new
from cascade.runtime.legacy.strategies import (
    GraphExecutionStrategy,
    VMExecutionStrategy,
)
from cascade.spec.runtime import ExecutionContext
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/__init__.py
~~~~~
~~~~~python.old
from .graph import GraphExecutionStrategy
from .vm import VMExecutionStrategy
from .base import ExecutionContext, ExecutionStrategy

__all__ = [
    "GraphExecutionStrategy",
    "VMExecutionStrategy",
    "ExecutionContext",
    "ExecutionStrategy",
]
~~~~~
~~~~~python.new
from .graph import GraphExecutionStrategy
from .vm import VMExecutionStrategy

__all__ = [
    "GraphExecutionStrategy",
    "VMExecutionStrategy",
]
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import TaskSkipped, TaskBlocked
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.legacy.strategies.base import ExecutionContext


class GraphExecutionResult:
~~~~~
~~~~~python.new
from cascade.runtime.services.observability.events import TaskSkipped, TaskBlocked
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.spec.runtime import ExecutionContext


class GraphExecutionResult:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~
~~~~~python.old
from cascade.reflection import ReflectionAnalyzer


from cascade.runtime.legacy.strategies.base import ExecutionContext


class VMExecutionStrategy:
~~~~~
~~~~~python.new
from cascade.reflection import ReflectionAnalyzer


from cascade.spec.runtime import ExecutionContext


class VMExecutionStrategy:
~~~~~

### 下一步建议
我们已经完成了接口的迁移。建议下一步运行现有的测试套件（尤其是 `tests/runtime` 下的测试），确保由于路径变更导致的导入错误已全部修复。如果测试通过，我们可以创建一个 `[COMMIT]` 计划来永久化这次重构。
