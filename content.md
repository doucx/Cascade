Excellent. We're moving on to the second milestone of our architecture refactoring. This is where the new protocol becomes tangible.

I will now generate the plan to migrate the existing `pause` logic into our first concrete handler, `PauseConstraintHandler`, and add the enhanced scope-matching capabilities as defined in the roadmap.

## [WIP] refactor(runtime): Implement PauseConstraintHandler and decouple from manager

### 用户需求
根据“路线图：可插拔约束处理器架构 (v1.0)”，完成“里程碑 2：迁移现有逻辑 (The Migration)”。

### 评论
这是新架构的第一次“试驾”。通过将 `pause` 逻辑从核心 `ConstraintManager` 迁移到一个独立的、可测试的 `PauseConstraintHandler` 中，我们不仅证明了新协议的可行性，还立即获得了价值：我们现在可以实现更精细的、基于作用域（Scope）的控制，例如暂停单个任务，这是旧的硬编码实现无法做到的。

### 目标
1.  在 `cascade/runtime/constraints/` 包中创建一个新的 `handlers.py` 文件。
2.  在该文件中实现 `PauseConstraintHandler`，使其符合 `ConstraintHandler` 协议。
3.  `PauseConstraintHandler` 的 `check_permission` 方法必须实现完整的作用域匹配逻辑（支持 `global` 和 `task:<task_name>`）。
4.  从 `ConstraintManager` 的 `check_permission` 方法中移除旧的、硬编码的 `pause` 逻辑，为下一步的调度器重构做准备。

### 基本原理
我们采用“Strangler Fig”模式进行重构。首先，我们构建新的功能单元 (`PauseConstraintHandler`)，使其具备比旧实现更强的功能（即作用域匹配）。然后，我们“杀死”旧的实现，即从 `ConstraintManager` 中删除硬编码的 `if constraint.type == "pause"` 逻辑。

为了保持增量重构的安全性，在 `ConstraintManager` 成为一个完整调度器之前（里程碑 3），我们暂时将其 `check_permission` 方法修改为总是返回 `True`。这确保了在重构的中间步骤中，系统保持可运行状态，尽管约束功能会暂时失效，直到下一个里程碑完成。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/config #scope/api #ai/instruct #task/domain/runtime #task/object/constraint-system #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `PauseConstraintHandler`

我们创建新的 `handlers.py` 文件，并实现 `PauseConstraintHandler`。它将包含处理 `pause` 约束的所有逻辑，包括对 `global` 和 `task:` 作用域的匹配。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
from typing import TYPE_CHECKING

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


if TYPE_CHECKING:
    from .manager import ConstraintManager


class PauseConstraintHandler(ConstraintHandler):
    """
    Handles the 'pause' constraint type.
    It can pause execution globally or for a specific task.
    """

    def handles_type(self) -> str:
        return "pause"

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # Project-specific scope (placeholder for future implementation)
        # if scope.startswith("project:"):
        #     ...

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True
~~~~~

#### Acts 2: 从 `ConstraintManager` 中移除硬编码逻辑

现在我们修改 `ConstraintManager`，移除旧的 `pause` 检查。在下一个里程碑中，这里将被新的调度逻辑取代。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.
        """
        # TODO: Implement expiry logic (check constraint.expires_at)
        # TODO: Implement scope matching (e.g., "task:task_name")

        for constraint in self._constraints.values():
            # Check for global pause
            if constraint.type == "pause" and constraint.scope == "global":
                return False  # Execution is not permitted

        # If no blocking constraints are found, permit execution.
        return True
~~~~~
~~~~~python
    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.
        """
        # TODO: This will be replaced by the dispatcher logic in the next milestone.
        # For now, it permits all execution to allow incremental refactoring.
        return True
~~~~~

### 下一步建议
逻辑迁移已经完成。现在 `ConstraintManager` 是一个空壳，而 `PauseConstraintHandler` 已经准备就绪。下一步是**里程碑 3**，我们将重建 `ConstraintManager` 作为一个真正的调度中心，使其能够注册并调用我们刚刚创建的 `PauseConstraintHandler`。
