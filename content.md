好的，测试已通过，我们的基础组件及其交互得到了验证。现在我们回到主线任务，放心地为 `ConstraintManager` 赋予真正的控制能力。

我们将实施“全局暂停”功能。这是约束系统中最简单但也是最强大的功能之一，它将使我们能够通过外部指令完全暂停工作流的执行。

我将生成实现此功能的计划。

## [WIP] feat: 在 ConstraintManager 中实现全局暂停逻辑

### 用户需求
在 `ConstraintManager` 的 `check_permission` 方法中实现约束评估逻辑，使其能够响应“全局暂停”指令。

### 评论
这是我们构建的反馈回路首次闭合的时刻。至此，`Engine` 不仅能接收指令，还能根据指令改变其核心调度行为。这个功能的实现，标志着 Cascade 从一个纯粹的执行引擎，向一个可被实时操控的自适应系统迈出了关键的第一步。

### 目标
1.  修改 `ConstraintManager.check_permission` 方法。
2.  新的逻辑需要遍历所有已存储的 `GlobalConstraint`。
3.  如果发现存在一个类型为 `pause` 且作用域为 `global` 的有效约束，该方法必须返回 `False`。
4.  如果遍历完所有约束都没有发现匹配的暂停指令，则返回 `True`。

### 基本原理
我们将采用一个简单的迭代模型。`check_permission` 在每次被调度器调用时，都会实时检查当前的约束集合。通过查找一个具有特定 `type` 和 `scope` 组合的 `GlobalConstraint` 对象，我们可以实现对全局暂停指令的识别。这种实现方式简单、直接，并且为未来扩展到更复杂的约束类型（如速率限制、任务级暂停）提供了清晰的模式。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/constraints #scope/core
#ai/instruct
#task/domain/runtime #task/object/constraint-system #task/action/implementation #task-state/continue

---

### Script

#### Acts 1: 实现约束评估逻辑

我们将修改 `constraints.py` 文件中的 `check_permission` 方法，替换掉原有的占位符逻辑。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints.py
~~~~~
~~~~~python
    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.

        TODO: Implement full evaluation logic based on constraint scope and type.
              For now, it's permissive.
        """
        # Placeholder logic: always allow execution
        return True
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

### 下一步建议
我们已经成功实现了全局暂停的核心逻辑。现在，为了验证整个反馈回路是端到端工作的，我们需要**创建一个新的集成测试**。

这个测试将：
1.  启动一个包含多个任务的 `Engine`。
2.  在运行中途，通过 `MockConnector` 发送一个“全局暂停”的约束指令。
3.  断言在收到指令后，后续的任务不再被执行，并且 `Engine` 的 `run` 方法会一直阻塞（直到我们手动取消它）。
4.  （可选）发送一个“解除暂停”的指令，并断言任务恢复执行。

这个测试将是整个第三阶段功能的一个关键里程碑验证。如果你同意，我将立即着手创建这个测试计划。
