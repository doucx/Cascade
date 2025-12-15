好的，事件发布功能已完成并验证通过。现在，我们将其作为一个完整的工作单元提交。

## [COMMIT] feat(runtime, event): Enhance observability with Resource lifecycle events

### 用户需求
将资源生命周期事件（`ResourceAcquired`, `ResourceReleased`）的实现提交到版本控制。

### 评论
通过将资源管理的操作（setup 和 teardown）转化为显式的、结构化的事件，我们极大地提升了系统的透明度。这不仅使得测试 `Engine` 的资源清理逻辑变得简单，也为未来的诊断、监控和审计工具提供了关键的数据源。这是一个小而精悍的改进，但对系统的可观测性有着巨大的长期价值。

### 目标
1.  将所有与资源事件相关的新建和修改文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git Commit。

### 基本原理
持续利用 Message Bus 模式，确保核心逻辑（`Engine`）与观测逻辑（日志、监控）之间的解耦。事件发布使得资源管理流程变得透明。

### 标签
#intent/build #flow/ready #priority/medium
#comp/runtime #comp/events #comp/tests
#concept/observability #concept/dependency-injection
#scope/core
#task/domain/core #task/object/observability #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Stage all changes

将所有与资源事件相关的修改添加到 Git 暂存区。

~~~~~act
git_add
~~~~~
~~~~~
src/cascade/runtime/engine.py
src/cascade/runtime/events.py
tests/test_di_and_resources.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime, event): Enhance observability with Resource lifecycle events

Introduces two new event types, `ResourceAcquired` and `ResourceReleased`, to the runtime Message Bus.

The Engine is updated to publish these events:
1. `ResourceAcquired` is published immediately after a resource's generator yields its instance (setup complete).
2. `ResourceReleased` is published after the generator is exhausted (teardown complete).

This enhancement provides critical observability into the resource lifecycle, allowing subscribers to monitor the setup time and failure status of external dependencies, which is crucial for debugging and performance profiling.

The integration tests were updated to assert the correct sequence of these events, ensuring that dependencies are acquired in forward order and released in reverse order.
~~~~~

### 下一步建议
我们继续 Cascade 阶段二的下一项核心任务：**一等公民的异步 (`async/await`) 支持**。

这个任务包含对 `Task`, `Executor`, 和 `Engine` 的核心协议修改。

我将拆解为以下子任务：
1. **规格与协议演进**: 修改 `@task` 装饰器和 `Executor` 协议，使其兼容异步。
2. **执行器升级**: 将 `LocalExecutor` 改造为支持同步/异步混合执行。
3. **引擎异步化**: 将 `Engine.run` 改造为 `async def`，并确保 `cascade.run()` 门面函数能正确启动 `asyncio` 事件循环。

如果你同意，我将从**规格与协议演进**开始。
