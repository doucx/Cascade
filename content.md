这是对上一步性能优化的一个关键记录点。性能测试数据显示我们成功地将 TCO 快速路径的性能恢复到了 100k TPS 以上，这证明了异步税已经被成功消除。

我将创建一个 `[COMMIT]` 计划来记录这次变更。

## [COMMIT] perf(runtime): 消除 TCO 快速路径中的异步税

### 用户需求
提交对 `GraphExecutionStrategy` 的性能优化，该优化旨在消除 TCO 快速路径中不必要的异步调用，恢复性能基线。

### 评论
本次提交是恢复 Cascade 引擎性能基线的关键一步。性能测试结果（超过 100k TPS）验证了将 `await` 调用从 TCO 热循环中剥离的巨大价值。这为后续的性能优化（尤其是针对 Heavy Path 的 JIT 结构化哈希）提供了一个可靠的、高标准的参照基准。

### 目标
通过 Git 提交，记录以下变更：将 `state_backend.clear()` 和 `asyncio.sleep(0)` 逻辑从 `GraphExecutionStrategy.execute` 的 TCO 循环末尾移除，并将其移动到 Slow Path 的图构建之前。

### 基本原理
TCO 快速路径的目标是零开销循环。任何 `await` 调用，即便是 `asyncio.sleep(0)`，也会强制进行上下文切换。将这些操作转移到只在缓存未命中时才触发的慢速路径，确保了 Fast Path 能够以接近裸 Python 循环的效率运行。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/tco-fast-path #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 提交性能优化变更

将修改后的 `graph.py` 文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
perf(runtime): Eliminate async tax in TCO fast path

The Zero-Overhead TCO fast path was severely degraded due to two unnecessary `await` calls (`state_backend.clear()` and `asyncio.sleep(0)`) at the end of every loop iteration. These calls forced an unnecessary event loop context switch on every hot-loop cycle.

The change moves these asynchronous clean-up/yield operations to the Slow Path (Graph rebuilding path) where the overhead is negligible, restoring the Fast Path performance to over 100k TPS.

This fulfills the "Phase Zero: Performance Baseline Optimization" requirement from the architecture roadmap.
~~~~~

### 下一步建议
性能基线现已恢复。我们应立即开始执行 **阶段一：基石重构 —— 统一哈希管道**。该阶段将 `HashingService` 引入，实现 `Structural Hash` 和 `Template Hash` 的彻底分离，为解决当前 Heavy Path 的性能瓶颈做架构准备。

我建议下一个计划的目标是：
1.  在 `packages/cascade-graph/src/cascade/graph/hashing.py` 中，定义并实现 `Template Hash` 的计算逻辑：它必须忽略所有字面量参数，只关注结构和依赖。
2.  更新 `GraphBuilder` 的 `_visit_lazy_result` 方法，确保它能够计算并存储 `Template Hash`。
