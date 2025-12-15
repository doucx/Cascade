简要回答
我们已完成运行时重构，将节点执行逻辑提取到独立方法并增强了可观测性。现在将创建提交，正式提交此改进。

## [COMMIT] refactor(engine): Extract node execution logic and add TaskRetrying event

### 用户需求
1.  重构 `Engine.run`，将单个节点的执行逻辑（包括缓存和重试策略）提取到 `_execute_node_with_policies` 私有异步方法中。
2.  在任务重试前引入并发布新的 `TaskRetrying` 事件，增强可观测性。
3.  更新 `HumanReadableLogSubscriber` 以支持新的 `TaskRetrying` 事件。

### 评论
本次提交是 Cascade 架构健康的关键一步。它显著解耦了 `Engine` 的核心调度循环和单个任务的策略执行逻辑，为未来在主循环中引入更复杂的控制流（如条件执行和动态路由）奠定了坚实的基础。同时，`TaskRetrying` 事件极大地改善了开发者在调试失败任务时的体验。

### 目标
1.  提交对 `src/cascade/runtime/events.py` 的修改。
2.  提交对 `src/cascade/runtime/subscribers.py` 的修改。
3.  提交对 `src/cascade/runtime/engine.py` 的修改。
4.  创建一个 Git Commit。

### 基本原理
提取逻辑遵循了“单一职责原则”。通过将任务执行的复杂性封装起来，`Engine.run` 现在只关注于图的遍历和结果收集，变得更简洁。引入 `TaskRetrying` 事件使我们的日志和监控系统更加精细化。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/runtime #concept/executor #concept/history #scope/core
#ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Stage files

将所有修改过的文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/runtime/events.py
src/cascade/runtime/engine.py
src/cascade/runtime/subscribers.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): Extract node execution logic and add TaskRetrying event

This refactoring implements two key architectural improvements:

1.  **Engine Refactoring**: The complex logic for executing a single graph node (including cache checking, retry loop, and event publishing) has been extracted from `Engine.run` into a new private asynchronous method, `_execute_node_with_policies`.
    *   This dramatically simplifies the `Engine.run` loop, making it easier to integrate future control flow features like conditional execution (`run_if`).

2.  **Enhanced Observability**: Introduced `TaskRetrying` event in `cascade.runtime.events` and added logging support for it in `HumanReadableLogSubscriber`.
    *   The engine now publishes this event right before retrying a failed task, providing developers with clear, real-time feedback on the retry process.

This aligns the runtime with best practices for handling complex execution policies and improves DX.
~~~~~

### 下一步建议
我们已经完成了运行时重构。接下来，我们将正式开始实施 Cascade 阶段三：增强表现力与动态工作流。

根据执行计划，下一步是实现轻量级调试工具 **`cs.dry_run`**，它将允许用户在不运行任何代码的情况下，预览拓扑排序后的执行计划。
