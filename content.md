太棒了，我们已经成功打通了新架构的第一条关键路径。现在，我们将这些改动作为一个完整的逻辑单元提交到 Git。

## [COMMIT] feat(core): 实现显式控制流并废除隐式 TCO 机制

### 用户需求
按照 Cascade 架构演进路线图，废除基于 AST 分析的隐式尾调用优化（TCO），引入显式的 `cs.Jump`、`cs.bind` 和 `cs.select_jump` 原语。同时清理内核中过时的静态分析逻辑，并建立运行时完整性校验。

### 评论
这是一次具有里程碑意义的重构。我们移除了内核中最复杂且脆弱的 AST 探测部分，将控制权交还给开发者。这不仅简化了 `GraphBuilder` 和执行策略，还显著提升了系统的可预测性。通过 `GraphExecutionResult` 引入的上下文追踪机制，彻底解决了在复杂图中跳转时的歧义问题。

### 目标
1.  提交 `cs.Jump` 和 `cs.JumpSelector` 的 Spec 定义。
2.  提交 `GraphBuilder`、`Node` 模型和 `HashingService` 的简化实现。
3.  提交重写后的 `GraphExecutionStrategy`，支持带上下文的显式跳转。
4.  提交 `LocalExecutor` 中的运行时完整性校验逻辑（禁止任务返回 `LazyResult`）。
5.  提交全新的显式控制流与静态完整性测试套件，并移除已废弃的旧测试。

### 基本原理
我们确立了“任务只计算，不构建图”的硬性约束。通过在运行时拦截非法的 `LazyResult` 返回值并强制使用 `Jump` 信号，我们将 Cascade 从一个动态拼凑图的引擎转变为一个确定性的状态转移框架。双层身份体系的基础（Instance Hash 与 Template Hash）已在 `HashingService` 中稳固。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/graph #comp/spec #comp/sdk #concept/control-flow #scope/core #ai/instruct #task/domain/engine #task/object/control-flow #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交核心架构变更

我们将添加所有新增和修改的文件，并移除已删除的文件。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): implement explicit control flow and deprecate implicit TCO

This commit marks a major strategic shift in Cascade's core programming model, 
moving from fragile AST-based implicit recursion to a deterministic, 
explicit state transition model.

Key Changes:
- Primitives: Introduced 'cs.Jump', 'cs.bind', and 'cs.select_jump' for 
  explicitly defining iterative loops and state machines.
- Safety: Added a runtime guard in LocalExecutor that forbids tasks from 
  returning LazyResult instances, enforcing the "tasks calculate, graphs build" 
  principle.
- Strategy: Completely rewrote GraphExecutionStrategy to use a contextual 
  GraphExecutionResult, eliminating ambiguity in jump source identification.
- Cleanup: Removed the 'ast_analyzer' module and all associated implicit TCO 
  caching logic ('_cycle_cache').
- Tooling: Simplified 'cs.visualize' by removing shadow node and potential 
  edge styles.
- Testing: Replaced legacy TCO tests with a new suite focused on explicit 
  jumps and graph integrity.

This consolidation paves the way for the unified dual-layer identity and 
caching system in Phase 4.
~~~~~

### 下一步建议
我们已经圆满完成了路线图的前三个阶段（引入原语、内核集成、清理旧体系）。

现在，我们站在了 **阶段四：`[Optimization]` - 建立统一的双层身份体系** 的起点。我的建议如下：

1.  **重构 HashingService**: 虽然它在之前的步骤中被保留了，但它的职责现在可以更加纯粹：只负责计算 `Instance Hash`。
2.  **实现 BlueprintHasher**: 创建一个新服务，专门用于计算 `Graph Blueprint Hash`（忽略字面量参数的拓扑哈希）。
3.  **集成计划缓存**: 在 `Engine` 中引入 `_plan_cache`，并修改执行逻辑，在 `Solver.resolve()` 之前先检查蓝图哈希，从而实现真正的“编译一次，运行无限次”。

准备好开始阶段四了吗？
