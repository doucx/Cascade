这是一个关键的里程碑。我们已经成功地将核心架构升级为异步，并解决了由此引入的重大功能性和性能问题。现在，我们将这些修改作为一个完整的逻辑单元提交。

## [COMMIT] refactor(core): 强制 StateBackend 异步化并消除性能开销

### 用户需求
将 StateBackend 协议异步化，并修复由此导致的功能逻辑中断和不当使用 `asyncio.to_thread` 导致的性能雪崩。

### 评论
本次提交是针对架构审计 P0 缺陷的系统性修复。它确立了 Cascade 核心 I/O 边界的异步契约，消除了未来因同步 I/O 阻塞事件循环的风险。同时，通过精确区分**阻塞 I/O** (Redis) 和**纯内存操作** (InMemory)，我们恢复了 TCO 快速路径的性能，避免了不必要的线程协调开销。所有核心运行时组件和测试用例已同步更新。

### 目标
提交所有已完成的 StateBackend 异步化、消费者适配和性能修复相关的代码，关闭第一阶段的重构。

### 基本原理
**协议层面**: 强制 `StateBackend` 协议为 `async def`，实现业务逻辑与 I/O 边界的明确分离。
**性能层面**:
1.  **Redis**: 保持使用 `await asyncio.to_thread` 包装，正确隔离同步网络 I/O。
2.  **InMemory**: 移除 `to_thread`，允许字典操作直接在事件循环中执行，以达到零开销，恢复 TCO 性能。
**功能层面**: 更新 `FlowManager`, `ArgumentResolver`, `NodeProcessor` 等组件，确保所有状态查询都正确使用了 `await`，从而恢复了条件执行和路由剪枝的逻辑正确性。

### 标签
#intent/refine #flow/done #priority/high #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/state-backend #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存所有功能性代码和测试修复

我们将所有更改的文件添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/protocols.py
packages/cascade-engine/src/cascade/adapters/state/in_memory.py
packages/cascade-engine/src/cascade/adapters/state/redis.py
packages/cascade-engine/src/cascade/runtime/flow.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
tests/engine/adapters/state/test_redis_state.py
tests/engine/adapters/state/test_in_memory_state.py
tests/engine/runtime/test_flow_manager.py
observatory/benchmarks/tco_performance.py
scripts/profile_entry.py
~~~~~

#### Acts 2: 执行提交

创建一个详尽的提交信息，记录本次重构的战略意义和所有主要变更。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Enforce async StateBackend protocol and fix performance regression

This systemic refactor addresses Architecture Defect B (IO boundary ambiguity) by making the StateBackend protocol fully asynchronous.

Key Changes:

1.  **Protocol Enforcement**: All methods in `StateBackend` are now `async def`.
2.  **Runtime Adaptation**: All consumers (`FlowManager`, `ArgumentResolver`, `NodeProcessor`, `GraphExecutionStrategy`) were updated to correctly `await` state operations, fixing numerous logic bugs where coroutine objects were incorrectly evaluated as `True`.
3.  **Performance Fix (Strategic Refinement)**: The initial use of `asyncio.to_thread` in `InMemoryStateBackend` was removed. This recovers high performance in TCO fast paths by preventing unnecessary thread context switching for pure-CPU dictionary operations, while maintaining `async def` compliance.
4.  **Backend Implementation**: `RedisStateBackend` correctly continues to use `asyncio.to_thread` to safely isolate true synchronous network I/O.
5.  **Testing**: Key tests (`test_flow_manager`, `test_in_memory_state`) were converted to async mode to validate the new protocol contract.

This commit establishes a robust, non-blocking I/O boundary for the core engine.
~~~~~

### 下一步建议
**诊断和修复 TCO 快速路径中的“异步税”**：

虽然 `InMemoryStateBackend` 的性能已恢复，但我们仍观察到 `stable_complex_loop` 中存在约 25% 的性能回归，我们已诊断出这是由于在 TCO 循环中**不必要的** `await state_backend.clear()` 和 `await asyncio.sleep(0)` 强制上下文切换所致。

我们已经完成了性能剖析工具的设置。下一步就是执行我们之前商定的战略：**在 `GraphExecutionStrategy` 中为 TCO 快速路径“减负”**，消除这些不必要的 `await`。
