我们将创建一个 `[COMMIT]` 计划，提交并发执行功能的最后一块修复和重构，包括对 `Engine` 错误处理逻辑的修正。

## [COMMIT] feat/fix(runtime): Implement staged execution and fix plan traversal

### 用户需求
1.  支持并发执行无依赖任务以提高性能。
2.  修复因分层执行计划（`List[List[Node]]`）引入后，在 `Engine` 异常处理中遍历计划时产生的 `AttributeError`。

### 评论
这个提交代表了 `Cascade` 运行时核心架构的重大升级。通过分层执行计划，我们将 `Cascade` 的执行模型从严格串行提升到并发。所有适配器（`NativeSolver`、`ResourceScanner`、`PreviewTool`）和错误处理逻辑都已更新以支持这种新的、更高效的调度结构。

### 目标
创建一个 Git 提交，包含以下文件的所有变更：
*   `src/cascade/runtime/protocols.py` (更新 `ExecutionPlan` 定义)
*   `src/cascade/adapters/solvers/native.py` (实现分层拓扑排序)
*   `src/cascade/runtime/engine.py` (支持分层执行和修复错误处理)
*   `src/cascade/tools/preview.py` (适配 Dry Run 工具)
*   `tests/adapters/solvers/test_native.py` (更新求解器测试)

### 基本原理
为了支持并发执行，`Solver` 现在返回一个阶段列表，每个阶段可以并行运行。`Engine` 使用 `asyncio.gather` 实现这种并发，并修正了所有依赖于旧的扁平列表假设的代码块（如资源扫描和异常查找）。

### 标签
#intent/build #intent/refine #flow/ready #priority/high
#comp/runtime #comp/engine #comp/tests #concept/concurrency #scope/core
#ai/instruct
#task/domain/runtime #task/object/execution-plan #task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有并发执行相关的变更

将涉及并发执行和修复的所有文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/runtime/protocols.py
src/cascade/adapters/solvers/native.py
src/cascade/runtime/engine.py
src/cascade/tools/preview.py
tests/adapters/solvers/test_native.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement staged execution for parallel task running

This is a major architectural upgrade that enables parallel execution of independent tasks within a workflow, significantly improving performance.

Key changes include:
1.  **ExecutionPlan Refactored**: Changed `ExecutionPlan` from `List[Node]` to `List[List[Node]]` (a list of execution stages).
2.  **NativeSolver**: Replaced `graphlib.TopologicalSorter` with a custom layered Kahn's algorithm implementation to generate optimized stages.
3.  **Engine Concurrency**: Updated `Engine._execute_graph` to use `asyncio.gather` to run all tasks within a single stage concurrently, introducing a barrier between stages.
4.  **Compatibility Fixes**: Updated `_scan_for_resources` and error handling logic to correctly traverse the nested plan structure, resolving `AttributeError` issues across the codebase.
5.  **Tooling/Tests**: Updated `dry_run` preview logic and `test_native.py` to assert the new staged output structure.
~~~~~

### 下一步建议
我们已经完成了并发执行的基础架构。现在，我们可以开始规划 **高级求解器 (`CSPSolver`)**，这是下一阶段的核心任务。

**下一步：实现 CSPSolver**

1.  **准备环境**: 在 `pyproject.toml` 中添加 `python-constraint` 可选依赖。
2.  **Solver 接口**: 实现 `CSPSolver`，它将负责在分层拓扑排序的基础上，根据任务的资源需求和系统总资源，对同一层内的任务进行重新分配，生成最优的、资源感知的并行阶段。

如果你同意，我将开始实现 `CSPSolver` 的基础结构。
