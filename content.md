我们已经完成了重构计划的最后一步：标准化 `Strategy` 接口并引入 `ExecutionContext`。

通过这一改动，我们成功地为 `Engine` 和执行策略之间建立了一个稳定且可扩展的契约。现在，我们将这些变动正式提交，标志着本次“解耦 Engine 与 Graph”重构任务的圆满完成。

## [COMMIT] refactor(engine): standardize ExecutionStrategy interface with ExecutionContext

### 用户需求
完成 `ExecutionStrategy` 接口的标准化重构并提交。

### 评论
引入 `ExecutionContext` 是一个典型的架构优化动作。它将执行期的横切关注点（如 run_id, state_backend, resources）从函数签名中抽离出来，不仅清理了代码，也为未来支持多租户、分布式追踪或更复杂的资源隔离机制打下了基础。至此，整个重构计划的所有目标均已达成。

### 目标
1. 将 `strategies/base.py` (新文件/修改)、`strategies/graph.py` 和 `engine.py` 的变动添加到 Git 暂存区。
2. 创建一个详细的提交记录，说明接口标准化的目的和 `ExecutionContext` 的引入。

### 基本原理
按照重构计划，最后一步的提交应当标志着宏观任务的结束。通过统一接口，我们极大地降低了未来接入 v3.0 物理执行引擎（VM/Reactor）时的接口适配成本。

### 标签
#intent/refine #flow/ready #priority/medium #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/engine-graph-decoupling #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交接口标准化变更

我们将所有涉及接口变动的文件添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/strategies/base.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): standardize ExecutionStrategy interface with ExecutionContext

Standardized the 'ExecutionStrategy' protocol by replacing the long list of execution-time arguments with a single 'ExecutionContext' parameter object.

Changes:
- Defined 'ExecutionContext' in 'strategies/base.py' to encapsulate run_id, state_backend, params, run_stack, and active_resources.
- Updated 'ExecutionStrategy.execute' protocol signature to use 'ExecutionContext'.
- Refactored 'GraphExecutionStrategy.execute' to unpack values from the context.
- Updated 'Engine.run' to instantiate the context and pass it to the strategy.

This improvement stabilizes the engine-strategy contract and enhances the extensibility of the runtime context without breaking the interface in the future.
~~~~~

### 下一步建议
- **全面测试**: 建议运行 `pytest` 以验证所有现有的集成测试是否依然通过，特别是涉及复杂工作流和资源管理的测试。
- **架构审查**: 本次重构大幅度清理了 `Engine` 层。下一步可以考虑审查 `cascade-graph` 层，看是否能进一步简化 `Node` 的序列化逻辑。
