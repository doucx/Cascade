好的，既然那段死代码仅存在于被删除的冗余文件中，我们的任务已经超预期完成：不仅清理了死代码，还移除了具有误导性的重复实现。

现在我们将这个清理动作作为一个完整的工作单元进行提交。

## [COMMIT] refactor(engine): 移除冗余的 GraphExecutionStrategy 实现

### 用户需求
移除 `cascade-engine` 中多余的 `GraphExecutionStrategy` 实现，并清理其中包含的过时隐式 TCO 逻辑。

### 评论
这次清理显著减少了架构上的“噪音”。通过保留位于 `cascade.runtime.strategies.graph` 的唯一、优化过的实现，我们确保了引擎在处理控制流时只有一条逻辑路径（即 `cs.Jump`），同时也消除了开发者对两个类似实现可能产生的困惑。

### 目标
提交删除 `packages/cascade-engine/src/cascade/strategies/graph.py` 的操作。

### 基本原理
根据架构审计的结果，该文件是一个历史遗留的重复版本。通过将其删除，我们既解决了死代码问题（处理任务返回 `LazyResult` 的逻辑），也统一了引擎的调度策略实现。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #concept/tco #scope/core 
#ai/instruct 
#task/domain/engine #task/object/graph-execution #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交冗余文件清理

我们将清理后的变更添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/strategies/graph.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): remove redundant GraphExecutionStrategy implementation

Removed `packages/cascade-engine/src/cascade/strategies/graph.py` which was a redundant implementation of the execution strategy. This file contained legacy implicit TCO logic (attempting to process LazyResult as a return value) that is now forbidden by the LocalExecutor.

The engine now strictly uses the optimized version in `cascade.runtime.strategies.graph`, ensuring a single, clear path for control flow transitions via `cs.Jump`.
~~~~~

### 下一步建议
- **架构审计**: 建议继续审查 `cascade-engine/src/cascade/runtime/strategies/graph.py` 中剩余的逻辑，确保其 `_execute_hot_node` 优化路径与最新的 `LocalExecutor` 异常抛出逻辑完全对齐。
- **性能测试**: 进行一次回归性能测试，确认移除冗余文件和相关逻辑后，热循环 TCO 的 TPS 指标保持稳定。
