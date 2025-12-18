好的，我将根据您的请求，生成一个 `[COMMIT]` 计划来固化这次重要的架构优化。

## 好的，我们已经完成了确定性调度机制的实现和缺陷修复。现在将作为一个完整的逻辑单元提交。

## [COMMIT] refactor(runtime): Replace busy-waiting with event-driven synchronization

### 用户需求
将 `Engine` 主调度循环中，因任务被约束推迟而产生的 `asyncio.sleep(0.1)` 忙等待，替换为一个高效的、基于 `asyncio.Event` 的精确唤醒机制，以提高系统效率和稳定性。

### 评论
这是一项至关重要的性能和架构改进。它将调度器的行为从脆弱的、轮询式的“忙等待”模式，升级为健壮的、事件驱动的“静默等待”模式。特别是，我们通过在 `_on_constraint_update` 的 `finally` 块中调用唤醒事件，解决了 `resume` 命令导致的永久挂起问题，确保了约束变更的确定性通知。这使得 `Engine` 的调度循环在面对大量阻塞任务时，几乎不消耗 CPU 资源。

### 目标
1.  提交对 `Engine` 中调度循环的优化（用 `self._wakeup_event.wait()` 取代 `asyncio.sleep(0.1)`）。
2.  提交对 `_on_constraint_update` 的修正，确保在添加、更新或移除（`resume`）约束时，调度循环都能被正确唤醒。

### 基本原理
调度逻辑现在是确定性的：只有外部事件（通过 MQTT 接收到的约束变更）才会唤醒等待的调度器。这显著减少了调度器在空闲或受限状态下的 CPU 消耗，是构建高性能、可扩展的控制平面的基石。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/sync #scope/core #ai/instruct #task/domain/runtime #task/object/scheduler #task/action/optimization #task/state/end

---

### Script

#### Acts 1: 提交对 Engine 调度循环和唤醒机制的修改

将 `engine.py` 文件添加到 Git 暂存区，并执行一次包含详细性能改进的提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Replace busy-waiting with event-driven synchronization

The engine's scheduling loop previously relied on `asyncio.sleep(0.1)` when all pending tasks were deferred by constraints (busy-waiting).

This change refactors the engine to use `asyncio.Event` (`_wakeup_event`):

1.  **Eliminates Busy-Waiting**: The scheduler now `await self._wakeup_event.wait()` to efficiently block, consuming minimal CPU.
2.  **Deterministic Wakeup**: The `_on_constraint_update` callback is modified to call `self._wakeup_event.set()` in a `finally` block, guaranteeing that any constraint change—whether adding a new constraint or removing one via a resume command (empty payload)—will reliably wake the scheduler to re-evaluate tasks.

This significantly enhances the performance and robustness of the control plane, particularly under heavy constraint load.
~~~~~

### 下一步建议
我们已经解决了调度循环的性能问题（P0）。下一个关键的架构任务是解决 **运维安全** 问题：

-   **下一个关键任务**: **实现约束过期逻辑 (TTL)**。在 `ConstraintManager` 中集成 `expires_at` 的检查和自动移除功能，确保发布的约束不会永久阻塞系统，从而消除运维安全隐患。
