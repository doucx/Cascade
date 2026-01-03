好的，重构工作已经按计划完成。现在我将生成一个 `[COMMIT]` 计划，将这些逻辑分层的变动正式提交到版本控制系统中。

## [COMMIT] refactor(engine): split NodeProcessor logic into micro-pipeline helpers

### 用户需求
完成对 `NodeProcessor` 的内部逻辑拆分，并进行提交。

### 评论
这次重构虽然没有改变任何外部行为，但在架构演进上具有重要意义。通过将“执行”与“结果处理”分离，我们成功地在代码层面实现了 v3.0 “三连体”架构的逻辑原型。这极大提高了代码的可读性，并为后续可能的单元测试优化提供了便利。

### 目标
1. 将 `packages/cascade-engine/src/cascade/runtime/processor.py` 的变动添加到 Git 暂存区。
2. 创建一个清晰、符合规范的提交记录，说明此次重构的目的和结构变化。

### 基本原理
遵循“单次提交仅包含逻辑相关变更”的原则。由于我们已经验证了代码结构的正确性且未引入功能性变化，现在是将其作为一个稳定的逻辑单元入库的最佳时机。

### 标签
#intent/refine #flow/ready #priority/medium #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/engine-graph-decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 提交重构代码

我们将修改后的 `processor.py` 文件添加到 Git，并提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): split NodeProcessor into micro-pipeline helpers

Refactored the monolithic '_execute_internal' method into smaller, single-responsibility private methods:
- '_execute_core': Handles the raw execution via the executor (Worker).
- '_handle_successful_outcome': Manages post-success events and caching (Stainer-Success).
- '_handle_failed_outcome': Manages retries and failure reporting (Stainer-Failure).

This structural change aligns the runtime execution logic with the upcoming v3.0 architecture (Bleacher-Worker-Stainer) and improves overall maintainability.
~~~~~

### 下一步建议
我们现在已经完成了重构计划的前三步。下一步建议开始执行：
- **步骤 4：标准化 `Strategy` 接口**：定义一个更严格的 `ExecutionStrategy` 协议，并进一步减少 `Engine` 对具体执行细节的感知。
