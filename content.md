好的，我收到了测试结果。分析如下：

1.  **`test_engine_pauses_on_global_pause_constraint` 失败**: 这是**预料之中**的。在我上一步的重构中，我们故意从 `ConstraintManager` 中移除了硬编码的 `pause` 逻辑，并用一个临时的 `return True` 替换了它。这个测试的失败恰恰证明了我们的解耦是成功的，现在 `ConstraintManager` 确实不再处理 `pause` 逻辑了。修复这个问题需要我们继续执行路线图的下一个里程碑。

2.  **`test_cli_generator_from_context` 失败**: `TypeError: 'module' object is not callable`。这是一个意外的、但很重要的发现。原因是 `cascade-py` 库试图导出一个名为 `cli` 的函数 (`cs.cli`)，但我们的新包结构（`cascade-cli-controller`, `cascade-cli-observer`）已经建立了一个名为 `cascade.cli` 的命名空间包（模块）。这导致了名称冲突。Python 的导入系统优先将 `cascade.cli` 解析为模块，因此当我们尝试调用 `cs.cli(...)` 时，实际上是在尝试调用一个模块，从而引发了 `TypeError`。

我将生成一个计划，同时解决这两个问题。我们将首先修复命名冲突，然后完成约束系统重构的第三和第四里程碑，以修复暂停功能。

## [WIP] fix(cli, runtime): 修复 CLI 命名冲突并完成约束处理器重构

### 错误分析
1.  **CLI 命名冲突**: `cascade-py` 中的 `cascade.tools.cli.cli` 函数与 `cascade-cli-*` 包创建的 `cascade.cli` 命名空间包存在命名冲突。最清晰的解决方案是将该函数重命名为一个更具描述性的名称，如 `create_cli`，以消除歧义。
2.  **约束功能中断**: `ConstraintManager.check_permission` 方法在上一个里程碑中被故意清空，导致全局暂停功能失效，测试失败。这是重构过程中的一个预期步骤。现在的任务是完成路线图的后续里程碑，将其重建为一个可插拔的调度器，并注册 `PauseConstraintHandler` 来恢复功能。

### 用户需求
修复所有失败的测试，并完成 `ConstraintManager` 的重构。

### 评论
这次的测试失败非常有价值。它不仅验证了我们重构的正确性（约束功能确实被移除了），还暴露了一个潜在的、会导致用户混淆的 API 命名问题。通过一次性解决这两个问题，我们将使代码库更加健壮和清晰，并完成一个重要的架构改进。

### 目标
1.  将 `cascade.tools.cli.py` 中的 `cli` 函数重命名为 `create_cli`。
2.  更新 `cascade/__init__.py` 中的导入和导出，以反映此更改。
3.  更新 `tests/cli/test_cli.py` 以使用新的 `cs.create_cli` 函数。
4.  **(里程碑 3)** 重构 `ConstraintManager`，使其成为一个处理器调度中心，包含 `register_handler` 方法和新的 `check_permission` 调度逻辑。
5.  **(里程碑 4)** 在 `Engine` 的初始化过程中，实例化 `PauseConstraintHandler` 并将其注册到 `ConstraintManager` 中。

### 基本原理
我们首先通过重命名解决简单的命名冲突问题。然后，我们继续执行“可插拔约束处理器”路线图。`ConstraintManager` 将不再包含任何具体的约束逻辑，而是维护一个从约束类型到处理器的映射。其 `check_permission` 方法将遍历所有活动的约束，查找对应的处理器，并委托其进行评估。最后，我们在 `Engine` 层面将所有部件组装起来，恢复并增强暂停功能。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/cli #comp/runtime #concept/config #scope/api #ai/instruct #task/domain/runtime #task/object/constraint-system #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 CLI 命名冲突

我们将 `cli` 函数重命名为 `create_cli` 来解决与 `cascade.cli` 命名空间包的冲突。

首先，重命名 `tools/cli.py` 中的函数。
~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/cli.py
~~~~~
~~~~~python
def cli(target: "LazyResult[Any]") -> Callable[[], None]:
    """
    A factory that generates a Typer-based command-line interface for a Cascade workflow.
~~~~~
~~~~~python
def create_cli(target: "LazyResult[Any]") -> Callable[[], None]:
    """
    A factory that generates a Typer-based command-line interface for a Cascade workflow.
~~~~~

然后，更新 `__init__.py` 以导出新名称。
~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from cascade.graph.serialize import to_json, from_json
~~~~~
~~~~~python
# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",  # Now the factory function
    "Env",  # New factory function
    "run",
    "dry_run",
    "visualize",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
    "get_current_context",  # Exposed for testing/advanced usage
    "cli",
]
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",  # Now the factory function
    "Env",  # New factory function
    "run",
    "dry_run",
    "visualize",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
    "get_current_context",  # Exposed for testing/advanced usage
    "create_cli",
]
~~~~~

最后，更新测试用例以使用新函数名。
~~~~~act
patch_file
tests/cli/test_cli.py
~~~~~
~~~~~python
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.cli(target)

    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
~~~~~
~~~~~python
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.create_cli(target)

    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
~~~~~

#### Acts 2: 重建 ConstraintManager 为调度器 (里程碑 3)

我们将 `ConstraintManager` 改造为一个真正的调度器，它注册处理器并委托它们进行检查。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class ConstraintManager:
    """
    Manages a collection of global constraints that affect workflow execution.
    """

    def __init__(self):
        # Stores constraints by their unique ID for easy updates
        self._constraints: Dict[str, GlobalConstraint] = {}

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """
        Adds a new constraint or updates an existing one.
        """
        self._constraints[constraint.id] = constraint

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.
        """
        # TODO: This will be replaced by the dispatcher logic in the next milestone.
        # For now, it permits all execution to allow incremental refactoring.
        return True
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self):
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints against a task. If any handler denies
        permission, the task is deferred.
        """
        # TODO: Implement expiry logic (check constraint.expires_at)

        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted

        # If no handler denied permission, permit execution.
        return True
~~~~~

#### Acts 3: 组装系统：在 Engine 中注册处理器 (里程碑 4)

最后，我们在 `Engine` 初始化时，将 `PauseConstraintHandler` 注册到 `ConstraintManager` 中，完成整个流程的连接。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.adapters.state import InMemoryStateBackend
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import PauseConstraintHandler
from cascade.adapters.state import InMemoryStateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self.constraint_manager = ConstraintManager()
        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~python
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager()
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}
~~~~~

### 下一步建议
我们已经完成了 `ConstraintManager` 的重构，并修复了 CLI 的命名冲突。现在，所有测试都应该能通过了。我建议您立即运行测试套件来验证这一点。一旦验证通过，我们就可以认为这个任务已经完成，并可以继续路线图上的下一个功能，例如为并发或速率限制实现新的 `ConstraintHandler`。
