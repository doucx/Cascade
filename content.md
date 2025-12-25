我们已经成功实现了“语义化调度标签”功能，并修复了因引入多线程而产生的 SQLite 测试回归。现在，我将生成一个 `[COMMIT]` 计划，将这些涵盖契约定义、物理隔离实现以及稳定性修复的变更提交到仓库。

## [COMMIT] feat(engine): implement semantic scheduling modes with dedicated thread pools

### 用户需求
实现“计算与 IO 隔离”建议书中的第二部分：允许用户通过 `@task(mode="compute")` 显式声明任务属性，并让 `LocalExecutor` 利用独立的线程池（`blocking` vs `compute`）来执行这些任务，实现物理层面的负载隔离。

### 评论
这是 Cascade 运行时调度能力的重大进化。通过引入语义化的调度模式，我们将“意图声明”转化为“资源策略”。这不仅提高了系统在高并发、混合负载场景下的稳定性，也为未来根据 `mode` 自动申请资源（如 `cpu_slots`）打下了坚实的基础。同时，修复 SQLite 测试的过程也加深了我们对多线程环境下资源共享契约的理解。

### 目标
1.  提交 `cascade-spec` 中关于 `mode` 参数的定义变更。
2.  提交 `cascade-graph` 中关于 `execution_mode` 属性的传递逻辑。
3.  提交 `cascade-engine` 中 `LocalExecutor` 的多线程池路由实现。
4.  提交相关的静态验证测试和 E2E 隔离验证测试。
5.  提交针对 `test_sql.py` 的并发稳定性修复。

### 基本原理
我们在架构上完成了从“简单卸载”到“分类治理”的跨越。通过在 `LocalExecutor` 内部维护两个命名的 `ThreadPoolExecutor`，我们确保了不同性质的任务不会在同一个队列中互相阻塞。针对 SQLite 的修复证明了这种隔离是真实的，也提醒我们在编写 Provider 和 Resource 时需要考虑线程安全性和连接共享策略。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/spec #comp/graph #comp/tests #concept/executor #scope/perf #scope/dx #ai/instruct #task/domain/execution #task/object/scheduling-modes #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交语义化调度功能及其稳定性修复

我将把所有涉及契约定义、执行逻辑和测试修复的文件添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/task.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-engine/src/cascade/adapters/executors/local.py
tests/engine/graph/test_execution_mode.py
tests/engine/e2e/test_executor_modes.py
tests/sdk/providers/test_sql.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(engine): implement semantic scheduling modes with dedicated thread pools

Introduces semantic-aware task scheduling as part of the "Compute and IO Isolation" initiative.

Key changes:
1.  **Spec Layer**: Added `mode` parameter (defaulting to "blocking") to the `@task` decorator and `Task` class.
2.  **Graph Layer**: Added `execution_mode` to the `Node` model and updated `GraphBuilder` to propagate this metadata from the declaration to the static graph.
3.  **LocalExecutor Isolation**:
    - Replaced generic `asyncio.to_thread` with explicit routing to dedicated thread pools.
    - Maintains `_blocking_executor` (for IO) and `_compute_executor` (for CPU) to prevent workload starvation.
4.  **Stability Fixes**:
    - Updated `tests/sdk/providers/test_sql.py` to use SQLAlchemy `StaticPool` and `check_same_thread=False`, enabling in-memory SQLite to function correctly across different worker threads.
5.  **New Tests**:
    - `test_execution_mode.py`: Verifies static contract propagation.
    - `test_executor_modes.py`: Verifies physical execution isolation between modes.
~~~~~

### 下一步建议
我们已经完成了建议书中的前两个核心点。接下来，我们可以考虑实现：
- **动态流转语法糖 (`.offload()`)**: 允许在编排层动态决定调度策略，而不必修改原子任务的定义。
- **资源管理器联动**: 让 `mode="compute"` 自动请求 `cpu_slots` 资源，实现更智能的并发配额管理。

如果你准备好了，我建议下一步实施 `.offload()` 链式方法。
