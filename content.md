好的，我们已经完成了 `Router` 剪枝和 `FlowManager` 重构，修复了所有已知的并发和 ID 混淆问题。现在将这些修改作为一个完整的特性单元进行提交。

## [COMMIT] feat(runtime): Implement Router pruning and dedicated FlowManager

### 用户需求
解决 `Router` 的核心技术债务：当 `Router` 确定了执行路径后，应立即对未被选择的分支进行剪枝，以避免不必要的计算和资源浪费。

### 评论
本次提交是 `Cascade` 运行时架构的一次重大升级。为了支持动态剪枝，我们进行了关键的解耦：
1.  **引入 `FlowManager`**: 将控制流（跳过、剪枝）的职责从巨大的 `Engine` 循环中分离出来。
2.  **基于引用计数的剪枝**: `FlowManager` 使用动态引用计数（Demand）来跟踪节点的生命周期。当 `Router` 做出决策时，它减少未选中分支的需求。需求降为零的节点会被安全地标记为 `Pruned`，从而阻止其在后续阶段被调度执行。
3.  **修复并发错位**: 修正了 `Engine` 在并发执行过程中，由于剪枝导致的 Stage 结果与 Node 映射错位的致命 Bug。
4.  **支持 Param 选择器**: 修复了 `FlowManager` 无法解析 `cs.Param` 作为 `Router` 选择器的问题。

这极大地提升了 `Cascade` 在复杂、资源受限环境中的效率和表达能力。

### 目标
1.  正式引入 `EdgeType.ROUTER_ROUTE`。
2.  实现 `FlowManager`，并集成剪枝逻辑。
3.  确保 `Router` 在运行时能够正确地跳过所有未被选中的上游依赖。
4.  确保所有 `Router` 相关的测试通过。

### 基本原理
通过将控制流逻辑提升到 `FlowManager`，并在 `Engine` 任务完成时通知它（`register_result`），我们确保了剪枝决策发生在调度下一批任务之前。这是一种高效且健壮的控制流实现方式。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/runtime #comp/graph #concept/control-flow #concept/routing #scope/core #ai/instruct #task/domain/core #task/object/flow-manager #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加所有修改和新增的文件

~~~~~act
git_add
src/cascade/graph/model.py
src/cascade/graph/build.py
src/cascade/runtime/flow.py
src/cascade/runtime/engine.py
src/cascade/tools/visualize.py
tests/runtime/test_router_pruning.py
tests/spec/test_routing.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement Router pruning and dedicated FlowManager

Implements dynamic dependency pruning for unselected Router branches, significantly improving performance for conditional workflows involving expensive, long-running tasks.

Key Architectural Changes:
1.  **FlowManager**: Introduced `cascade.runtime.flow.FlowManager` to centralize all control flow logic (skipping, pruning, conditions).
2.  **Dynamic Pruning**: `FlowManager` uses a recursive, reference-counting mechanism (`downstream_demand`) to mark unneeded upstream nodes as `Pruned` immediately after the Router's selector result is available.
3.  **Graph Modeling**: Added `EdgeType.ROUTER_ROUTE` to distinctly mark potential dependency branches, separating them from standard implicit dependencies.
4.  **Concurrency Fix**: Corrected a critical misalignment bug in `Engine._execute_graph` where parallel execution and pruning could lead to results being mapped to the wrong nodes.

This resolves the long-standing debt regarding the inefficient execution of all branches in a routed workflow.
~~~~~

### 下一步建议
我们已经完成了核心控制流和动态图的最后一块拼图。接下来的工作应专注于**阶段四：生态系统与核心工具**，特别是：
1. **实现 Provider 插件的自动发现机制**：在 `cascade.providers` 中实现 `ProviderRegistry` 的 `_discover_entry_points` 逻辑。
2. **实现 `cs.template` Provider**：这是许多预编排场景（如生成 CI/CD 配置）的基础。
