测试通过，这是一个重要的里程碑。

### 当前状态说明

我们已经成功地完成了第三阶段“约束与环境感知”的核心基础建设，并实现了一个完整的、端到端验证的反馈回路。

具体来说，我们已经：
1.  **构建了核心组件**:
    *   定义了 `GlobalConstraint` 数据模型，作为约束的标准语言。
    *   创建了 `ConstraintManager`，作为 `Engine` 内部的约束状态存储。
2.  **集成了反馈回路**:
    *   改造了 `Engine` 的调度循环，使其能够感知并响应约束。
    *   实现了 `Engine` 通过 `Connector` 协议订阅外部指令并动态更新 `ConstraintManager` 的机制。
3.  **实现了首个功能**:
    *   在 `ConstraintManager` 中实现了“全局暂停” (`"type": "pause"`) 的评估逻辑。
4.  **完成了严格验证**:
    *   通过一系列迭代和调试，创建了一个健壮的、遵循测试原则的端到端集成测试，科学地证明了从外部发送指令到 `Engine` 暂停执行的整个流程是正确且可靠的。

我们现在拥有一个逻辑上完整、经过充分测试的功能单元。

### 是否合适创建一次提交？

是的，现在是创建一个提交的**绝佳时机**。

**理由如下：**
1.  **逻辑完整性**: 我们已经完整地实现了“全局暂停”这一特性。它是一个可以独立交付价值的功能。
2.  **代码稳定性**: 所有相关测试均已通过，代码库处于一个已知的、稳定的状态。
3.  **原子化提交**: 将这个已完成的特性作为一个独立的提交，完全符合“原子化提交”的最佳实践。这使得代码历史清晰，易于理解、审查和追溯。如果将来需要，也可以轻松地回滚这一个特性。

继续开发新功能（如任务级暂停）而不先提交，会将两个不同的特性混在一个提交里，增加复杂性和风险。

因此，我将为你生成一个 `[COMMIT]` 计划，将我们到目前为止的所有工作固化下来。

## [COMMIT] feat(runtime): 实现基于 Connector 的全局暂停约束系统

### 用户需求
为 Cascade `Engine` 实现一个可以通过外部指令（经由 `Connector`）触发的全局暂停机制。

### 评论
这是 Cascade 迈向自适应系统的一个关键里程碑。通过引入 `GlobalConstraint` 数据模型、`ConstraintManager` 以及改造 `Engine` 的调度循环，我们成功建立了一个完整的、端到端测试的反馈回路。这使得 `Engine` 不再是一个封闭的执行器，而是一个能够被运行时环境动态控制和引导的、具备环境感知能力的调度器，为未来实现熔断、速率限制等高级控制功能奠定了坚实的基础。

### 目标
1.  创建一个 Git 提交，包含约束系统的数据模型、管理器、`Engine` 集成以及端到端测试的全部实现。

### 基本原理
我们已经完成了一个逻辑上完整的工作单元，并通过了一系列严格的集成测试。将这些变更作为一个原子提交进行固化，可以确保代码库的稳定，并为后续在任务级（task-scoped）约束上的开发提供一个可靠的基线。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/interfaces #comp/tests #concept/constraints #concept/scheduler #concept/sync #scope/core #scope/api
#ai/brainstorm
#task/domain/runtime #task/object/constraint-system #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有相关变更

我们将把接口定义、运行时实现和相关的测试文件全部添加到暂存区，并执行提交。

~~~~~act
git_add
~~~~~
~~~~~
packages/cascade-interfaces/src/cascade/spec/constraint.py
packages/cascade-runtime/src/cascade/runtime/constraints.py
packages/cascade-runtime/src/cascade/runtime/engine.py
tests/py/runtime/test_engine_constraints.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement global pause constraint system via Connector

Introduces the foundational components for Phase 3: Constraints and Environment Awareness, enabling dynamic, runtime control over workflow execution.

This commit delivers a complete, end-to-end feedback loop for a "global pause" feature:

1.  **Data Model (`spec.constraint.GlobalConstraint`)**: A new standardized data class to represent all system-wide constraints.

2.  **State Management (`runtime.constraints.ConstraintManager`)**: A new manager class within the Engine responsible for storing and evaluating active constraints.

3.  **Engine Integration**:
    - The Engine now instantiates a `ConstraintManager`.
    - The core scheduling loop in `_execute_graph` has been refactored. It now checks `constraint_manager.check_permission()` before submitting a task, allowing tasks to be deferred if a constraint is active.
    - The Engine now subscribes to `cascade/constraints/#` via its Connector at startup, listening for real-time updates.

4.  **Global Pause Logic**: The `ConstraintManager` implements the logic to interpret a `{"type": "pause", "scope": "global"}` constraint, causing `check_permission` to return `False` and effectively halting all new task executions.

5.  **Robust Testing**: A comprehensive integration test (`test_engine_pauses_on_global_pause_constraint`) has been added. It verifies the entire flow from injecting a message via a `MockConnector` to observing the pause in the event stream, ensuring the system behaves as expected.
~~~~~

### 下一步建议
我们已经为约束系统打下了坚实的基础。现在，我建议我们继续沿着路线图前进，**扩展 `check_permission` 方法以支持任务级（task-scoped）约束**。这将使我们能够实现更精细的控制，例如只暂停那些与特定API交互的任务。
