太棒了！测试通过意味着我们的隐式卸载逻辑已经生效，能够正确地在不阻塞事件循环的情况下运行同步任务。现在，我将生成一个 `[COMMIT]` 计划，将这些变更作为一个逻辑单元提交到代码库。

## [COMMIT] feat(engine): implement implicit thread offloading for sync tasks

### 用户需求
实现“计算与 IO 隔离”建议书中的核心功能：框架应自动检测同步任务 (`def`)，并利用 `asyncio.to_thread` 将其卸载到独立线程中执行，以防止阻塞主事件循环，从而实现同步与异步任务的真正并发。

### 评论
这是一个重大的架构升级。通过消除同步阻塞任务对引擎的负面影响，我们极大地提高了 Cascade 运行时的鲁棒性和性能。开发者现在可以放心地在任务中使用同步库（如 `requests`, `pandas`, `time.sleep` 等），而不会导致整个智能体系统的遥测或控制逻辑响应中断。

### 目标
1.  将 `LocalExecutor` 的逻辑变更添加到暂存区。
2.  将新创建的 E2E 测试文件添加到暂存区。
3.  创建一个详细的 Git 提交。

### 基本原理
该功能的实现逻辑简单但高效：它将执行决策权从用户手中移交给了运行时引擎。通过这种方式，我们不仅解决了技术上的性能瓶颈，更重要的是降低了用户的心理负担，使其能专注于业务逻辑而非底层调度细节。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/perf #scope/dx #ai/instruct #task/domain/execution #task/object/offloading-feature #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交隐式线程卸载功能及其测试

我将把受影响的文件添加到 Git 暂存区，并创建一个内容详尽的提交记录。

~~~~~act
git_add
packages/cascade-engine/src/cascade/adapters/executors/local.py
tests/engine/e2e/test_offloading.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(engine): implement implicit thread offloading for sync tasks

Introduces automatic thread offloading for synchronous tasks within the LocalExecutor, as proposed in the "Compute and IO Isolation" roadmap.

Key changes:
1.  **LocalExecutor Enhancement**: The executor now checks the `is_async` flag of a Node. Synchronous tasks (defined with 'def') are automatically wrapped in `asyncio.to_thread`, ensuring they run in a separate thread pool and do not block the main event loop.
2.  **Performance & DX**: This allows standard Python blocking operations (like time.sleep, synchronous I/O, or heavy CPU tasks) to coexist with async tasks without starving the engine's core scheduling or telemetry logic.
3.  **New E2E Test**: Added `tests/engine/e2e/test_offloading.py` which strictly verifies that a 0.1s async task can finish before a 0.2s blocking sync task, proving parallel execution.

This change significantly improves the runtime's reliability in mixed-workload environments.
~~~~~

### 下一步建议
我们已经完成了建议书中的第一阶段任务。接下来，我们可以按照路线图继续推进：
- **语义化调度标签**: 允许用户显式标记 `@cs.task(mode="compute")` 以便使用专用的线程池。
- **性能诊断辅助**: 在 `dry_run` 阶段检测未标记卸载的潜在耗时同步任务并发出警告。

如果你准备好进行下一步，我建议先实施“语义化调度标签”，这能进一步优化资源分配策略。
