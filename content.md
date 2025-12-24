好的，我们已经成功完成了阶段四的核心任务，并修复了所有受影响的下游逻辑。

现在，我们拥有了一个逻辑清晰、职责分离的**双层身份体系**：
1.  **实例层 (Instance Level)**: 使用 `structural_id`（由 `HashingService` 计算），它包含所有字面量参数，用于精确的结果缓存。
2.  **结构层 (Blueprint Level)**: 使用 `Blueprint Hash`（由 `BlueprintHasher` 计算），它忽略字面量参数，只代表图的拓扑结构，用于高效的执行计划缓存。

我将生成 `[COMMIT]` 计划，将这些具有里程碑意义的改动保存到版本历史中。

## [COMMIT] refactor(core): Implement dual-layered identity system for caching

### 用户需求
根据架构演进路线图，实现双层身份体系以优化缓存策略：
1.  **实例哈希 (`structural_id`)**: 用于节点结果缓存。
2.  **蓝图哈希 (Blueprint Hash)**: 用于执行计划缓存。
并确保在该体系下，引擎能够对结构相同的工作流复用其执行计划。

### 评论
这次重构是 Cascade 向“确定性执行框架”迈进的关键一步。通过将一个具体节点实例的身份（用于结果缓存）与一个工作流拓扑结构的身份（用于计划缓存）进行物理分离，我们不仅简化了代码结构（移除了脆弱的 `template_id` 耦合），还极大地增强了系统的概念清晰度和可扩展性。

### 目标
1.  通过一个完整的提交，固化阶段四“统一身份体系”的所有改动。
2.  确保 `HashingService`、`BlueprintHasher`、`Engine` 和 `Serialization` 模块在新的架构下完全对齐。

### 基本原理
我们采用 TDD 流程完成了这次重构。通过先添加集成测试、再执行破坏性重构、最后通过引入专门的 `BlueprintHasher` 服务来修复系统，我们证明了新架构的正确性和有效性。这种“职责分离”模式确保了系统中的每一个哈希都有单一、明确的职责。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/dual-identity-system #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交双层身份体系的重构成果

我们将所有修改过的文件和新添加的测试文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
tests/engine/integration/test_plan_caching.py
tests/engine/runtime/test_flow_manager.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): implement dual-layered identity system for caching

This commit implements a unified, two-layer identity system that separates the
concerns of result caching and execution plan caching, fulfilling the goals
of Phase 4 of the architectural roadmap.

Key changes:
1.  **Identity Decoupling**: Removed 'template_id' from the Node model.
2.  **Instance Hash (Level 1)**: Refactored 'HashingService' to focus solely on
    computing the 'structural_id' (Instance Hash), which includes all literal
    parameters for precise results caching.
3.  **Blueprint Hash (Level 2)**: Introduced a new 'BlueprintHasher' service that
    computes a stable hash based on graph topology while ignoring literal inputs.
4.  **Engine Optimization**: Updated 'GraphExecutionStrategy' to use the new
    Blueprint Hash for indexing its JIT execution plan cache. This ensures
    that structurally identical workflows (e.g., 'add(1, 2)' and 'add(3, 4)')
    share the same plan, avoiding redundant Solver calls.
5.  **Robust Serialization**: Updated serialization logic and test mocks to align
    with the new single-hash Node model.
6.  **Verified via TDD**: Added a new integration test 'test_plan_caching.py'
    that explicitly asserts the reuse of execution plans for different instances
    of the same workflow structure.

This reorganization eradicates ambiguity in node identities and provides a cleaner,
more predictable foundation for future performance optimizations like AOT
compilation.
~~~~~

### 下一步建议
我们已经圆满完成了阶段四的任务。至此，[Cascade 架构演进路线图 - 显式控制流与统一身份体系](Cascade%20架构演进路线图%20-%20显式控制流与统一身份体系.md) 中定义的所有四个阶段均已成功结项。

**Cascade 现在是一个完全基于显式状态转移和确定性身份体系的运行时。**

接下来的重点可以转向：
1.  **性能压测**: 利用新架构对 TCO 快速路径和大规模图的缓存效率进行极限压力测试。
2.  **文档更新**: 基于最新的 API（`bind`, `Jump`, `select_jump`）更新用户手册，向开发者推广显式控制流模式。
3.  **功能扩展**: 考虑利用 `Blueprint Hash` 实现持久化的、跨进程的执行计划缓存（例如存储在 Redis 中）。

如果您有任何特定的新方向或需要进一步的优化，请指示！
