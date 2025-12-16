这是一个原子化的提交，它包含了 `CSPSolver` 的核心实现和两个关键的集成测试，验证了其在资源充足和资源不足时的调度行为。

## [COMMIT] feat(solver): 实现基于 CSP 的资源感知调度器

### 用户需求
将 `CSPSolver` 的核心 `resolve` 逻辑及其测试用例提交到 Git 历史中。

### 评论
`CSPSolver` 的实现是 `Cascade` 路线图中的一个里程碑，它为平台带来了真正的资源感知调度能力。通过采用迭代深度搜索，我们确保了在满足所有资源和依赖约束的同时，能够找到 Makespan 最小（即并行度最高）的执行计划。这为处理资源密集型工作流提供了必要的鲁棒性。

### 目标
创建一个 Git 提交，记录 `src/cascade/adapters/solvers/csp.py` 和 `tests/adapters/solvers/test_csp.py` 的变更。

### 基本原理
`CSPSolver` 是一个逻辑上完整的、经过充分测试的特性单元，应当拥有独立的提交历史。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/solver #scope/core #ai/instruct #task/domain/core #task/object/csp-solver #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 CSPSolver 核心逻辑与测试

将 `csp.py` 的实现和 `test_csp.py` 的集成测试添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/adapters/solvers/csp.py
tests/adapters/solvers/test_csp.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(solver): Implement resource-aware scheduling using CSPSolver

Implements the `CSPSolver` which uses Constraint Satisfaction Problem (CSP) techniques to resolve a dependency graph into an ExecutionPlan that is guaranteed to be resource-feasible in every stage.

Key aspects:
1.  **Iterative Deepening Search:** The solver iterates through possible stage counts (makespan) to find the minimum number of stages required, optimizing for parallelism.
2.  **Resource Constraint:** Introduces a custom global constraint to the CSP to ensure that the aggregate resource requirement of all tasks assigned to any single stage does not exceed the `system_resources` capacity.
3.  **Dependency Constraint:** Enforces topological order (`stage(A) < stage(B)` if `A -> B`).

This change transitions the scheduling logic from resource-blind (NativeSolver) to resource-aware (CSPSolver), preventing resource overcommitment and ensuring deterministic scheduling for constrained workflows.
~~~~~

### 下一步建议

我们已经完成了 `CSPSolver` 的核心实现。根据之前的技术债务分析，我们应该着手解决当前图模型中的实现债：消除对特殊边类型（如 `_constraint:` 和 `_implicit_dependency`）的魔法字符串依赖。

我建议下一个任务是：
1.  在 `cascade.graph.model` 中引入 `EdgeType` 枚举。
2.  在 `GraphBuilder` 中使用新的枚举来标记特殊边。
3.  在 `ArgumentResolver` 和 `LocalExecutor` 中更新检查逻辑，以使用枚举代替硬编码的字符串前缀检查。

如果你同意，我将生成下一个计划。
