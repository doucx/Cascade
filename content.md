好的，测试已通过。这意味着我们成功实现了尾调用优化 (TCO) 循环，并修正了资源管理器，使其能够根据资源作用域（Scope）在 TCO 循环的每个步骤中正确地释放和重新获取资源，从而防止资源泄漏。

现在我将生成一个 `[COMMIT]` 计划来封装这些变更。

## [COMMIT] feat(runtime): Implement Tail Call Optimization (TCO) and Scoped Resource Management

### 用户需求
实现“萤火计划” Milestone 1.2 中定义的内核重构：
1.  **TCO 递归**: 引擎应通过迭代而非递归来执行返回 `LazyResult` 的任务链，防止栈溢出，支持长运行 Agent。
2.  **Scoped Resource Management**: 确保 `scope="task"` 的资源在任务执行完毕后立即释放，而不是等到整个 `Engine.run` 结束后，解决长运行工作流中的资源泄漏问题。

### 评论
本次重构将 `Engine.run` 的核心逻辑从单次执行流程转换为了一个**持续求值循环**。这是 Cascade 从“流程引擎”向“自适应 Agent 运行环境”升级的关键一步。通过引入 `run_stack` 和 `step_stack` 的分层管理，我们以最小的侵入实现了高效的资源回收机制，完全满足了 TDD 测试用例的要求。

### 目标
创建一个 Git 提交，包含 `Engine.run` 的 TCO 逻辑和 `Engine._setup_resources` 的多作用域处理逻辑。

### 基本原理
通过在 `Engine.run` 中引入 `while True` 循环来处理 `LazyResult` 返回值，将逻辑递归转化为迭代，避免了 Python 的 `RecursionError`。同时，我们将资源初始化逻辑分离，使用一个长期存在的 `run_stack` 管理 `run` 作用域资源，以及一个在每次 TCO 迭代中重置的 `step_stack` 来管理 `task` 作用域资源。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #concept/resource #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/recursion-tco #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存并提交变更

将 `packages/cascade-runtime/src/cascade/runtime/engine.py` 文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/engine.py
tests/py/runtime/test_engine_recursion.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement TCO for LazyResult returns and Scoped Resource Management

This commit implements the foundation for long-running, iterative Cascade Agents by addressing deep recursion and resource leakage within the engine loop.

Key changes:

1.  **Tail Call Optimization (TCO) Loop**: `Engine.run` is converted into a `while True` loop that detects if a task returns a `LazyResult` or `MappedLazyResult`. If so, it uses that result as the next target in the iteration, avoiding stack overflow (`RecursionError`) and enabling recursive workflows that exceed Python's depth limit.
2.  **Scoped Resource Management**: Introduced `run_stack` (global cleanup) and `step_stack` (per-iteration cleanup) in `Engine.run`.
    *   Resources declared with `scope="task"` (the default for the TCO loop) are released when `step_stack` exits, ensuring resources are freed immediately after the task finishes its processing step, rather than holding them for the entire workflow duration.
3.  **Engine API Update**: `Engine.register` now stores the full `ResourceDefinition` to preserve the `scope` metadata.

This refactoring is a prerequisite for the "Firefly Test" and the implementation of `cs.wait` and `cs.recv`.
~~~~~

### 下一步建议
我们已经完成了内核的 TCO 重构。根据 **[萤火计划第一阶段：TDD 技术演进路线图](萤火计划第一阶段：TDD%20技术演进路线图.md)**，下一个里程碑是 **1.3：感知原语——时间 (`cs.wait`)**。

我建议我们开始实现 `cs.wait`，它将是一个封装了 `asyncio.sleep` 的原子任务，位于 `cascade-py/src/cascade/providers/time.py`（如果不存在，则创建一个新的 `time.py`）。这个任务将赋予 Agent 显式的时序控制能力。
