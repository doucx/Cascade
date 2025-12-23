好的，性能已经恢复并超越了基线，所有测试也都通过了。现在我们将把这些修复工作作为一个原子提交来完成。

### 简要回答
性能问题已成功解决。我将创建一个 `[COMMIT]` 计划，将相关的三个文件（`task.py`, `build.py`, `strategies.py`）添加到 Git，并撰写一份详细的提交信息，说明问题诊断和两阶段修复的过程。

## [COMMIT] perf(engine): Implement TCO fast path and AST caching for graph strategy

### 用户需求
解决 TCO 循环中的严重性能回归，并将修复作为一个完整的、原子化的提交记录到版本历史中。

### 评论
这次性能调优是一个典型的“剥洋葱”过程。最初的 AST 缓存修复了“重路径”的性能，但却暴露了“轻路径”中更深层次的哈希瓶颈。最终通过引入 TCO 快速通道，我们彻底解决了问题，使图形策略的 TCO 性能达到了历史最佳水平。

### 目标
创建一个 Git 提交，包含以下逻辑变更：
1.  在 `Task` 对象上添加 AST 分析结果的缓存字段。
2.  在 `GraphBuilder` 中实现对该缓存的填充和使用。
3.  在 `GraphExecutionStrategy` 中为简单的自递归 TCO 实现一个“快速通道”，以绕过结构化哈希。
4.  修正“快速通道”中的逻辑 Bug，确保其能正确处理非自递归的 TCO 转换。

### 基本原理
该提交通过两个核心优化来恢复 TCO 性能。首先，通过在 `Task` 对象上缓存 AST 分析结果，将源码解析的成本从每次图构建平摊为每个任务定义一次。其次，通过在 `GraphExecutionStrategy` 中为简单的自递归循环引入一个“快速通道”，将每次 TCO 迭代的开销从昂贵的对象树哈希（O(N)）降低为几次引用检查（O(1)），从而彻底消除了性能瓶颈。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #comp/graph #comp/spec #task/domain/performance #task/object/tco-loop #task/action/optimization #task/state/end

---

### Script

#### Acts 1: 提交性能修复

我们将把所有相关的修改添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/task.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
perf(engine): Implement TCO fast path and AST caching for graph strategy

Resolves a severe performance regression (2.5x-3.6x slowdown) in the graph-based TCO loop by implementing a two-part optimization strategy.

**Problem:**
1.  **AST Re-analysis:** The `GraphBuilder` repeatedly called `analyze_task_source` (involving I/O and AST parsing) on every TCO iteration for uncached, complex graphs (`heavy_complex_countdown` benchmark).
2.  **Repetitive Hashing:** For simple, cached graphs (`simple_countdown` benchmark), the `StructuralHasher` was invoked on every TCO iteration, creating significant overhead by traversing the object tree just to confirm the structure hadn't changed.

**Solution:**
1.  **Task-Level AST Caching:**
    - A `_potential_tco_targets` cache field was added to the `cascade.spec.task.Task` class.
    - `cascade.graph.build.GraphBuilder` now populates this cache on the first analysis and reuses the result on subsequent calls for the same task object, effectively amortizing the analysis cost to O(1) per task definition.

2.  **TCO Fast Path:**
    - A "fast path" was introduced in `GraphExecutionStrategy`.
    - It detects simple, self-recursive TCO calls by comparing the current task's object identity with the previously executed one.
    - When triggered, it completely bypasses the `StructuralHasher` and graph cache lookup, reusing the existing graph structure and only updating literal values. This reduces the per-iteration overhead to near-O(1).
    - A bug in the initial fast path logic that caused infinite loops with non-self-recursive TCO (A -> B) was also fixed by correcting the state update timing for `last_executed_task`.

**Impact:**
- `simple_countdown` benchmark TPS restored from ~1,300 to over 4,600.
- `heavy_complex_countdown` benchmark TPS restored from ~180 to over 415.
- All related tests, including `test_resource_release_in_recursion`, are now passing.
~~~~~
