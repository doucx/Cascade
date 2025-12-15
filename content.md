这是一个包含 `.run_if()` 完整功能的提交计划，包括核心逻辑和必要的执行器修复。

## [COMMIT] feat(core): Implement conditional execution with `.run_if()`

### 用户需求
实现 `.run_if()` 方法，允许根据一个上游任务（返回布尔值）的结果来决定当前任务是否执行。如果条件为 `False`，则当前任务及其所有下游任务应被跳过（剪枝）。

### 评论
该功能是构建动态、高效工作流的基础。核心实现涉及在 `GraphBuilder` 中创建特殊的控制流边，在 `Engine` 中实现 `_should_skip` 逻辑来处理条件判断和级联跳过，并在 `LocalExecutor` 中修复了参数传递错误，确保控制流边不会泄露到任务函数中。

### 目标
创建一个 Git 提交，将条件工作流所需的所有代码变更（spec, graph, runtime, executor fix, tests）整合为一个原子化的工作单元。

### 基本原理
按照 ACA 运行时协议，在功能测试通过后，应立即创建 `[COMMIT]` 计划以保持代码库历史的清洁和一致性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #comp/tests #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/conditional-workflow #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有文件变更

将 `run_if` 功能实现涉及的所有文件添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/spec/task.py
src/cascade/graph/build.py
src/cascade/runtime/engine.py
src/cascade/adapters/executors/local.py
tests/test_control_flow.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement conditional execution with .run_if()

This introduces conditional execution via the chainable method `.run_if(condition_result)`.

Key changes:
1. **Spec & Graph:** `LazyResult` stores the condition, and `GraphBuilder` creates a control flow edge using `arg_name="_condition"`.
2. **Engine Logic:** `Engine.run` now includes a skipping mechanism. It checks `_condition` task results and tracks `skipped_node_ids`. If a task's condition is `False`, or if any of its upstream dependencies were skipped, the task is skipped, ensuring proper graph pruning.
3. **Executor Fix (LocalExecutor):** The executor was patched to explicitly ignore edges with `arg_name="_condition"` during argument preparation, resolving a `TypeError` and preventing control flow information from leaking into user task functions.

The task object "conditional-workflow" is now considered complete.
~~~~~

### 下一步建议
我们已经完成了 `cs.File` 和 `.run_if()` 的实现。根据《Cascade 阶段三：增强表现力与动态工作流——执行计划》，接下来的重点是实现**动态路由 (`Router`) 和 任务映射 (`.map`)**。

我建议先从 **`cs.Router`** 开始，因为它在架构上相对独立，且能立刻解锁高级的数据源选择功能。
