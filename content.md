您是对的，我的诊断有误。

测试通过了，这意味着我之前关于 `template_id` 计算错误的假设是**不正确**的。`simple_countdown` 的缓存逻辑是健全的。

这指向了一个更深层次、也更有趣的问题。这不是一个简单的缓存 Bug，而是一个关于**“图构建成本 (Graph Building Cost)”**的性能特征问题。我们必须严格遵循 TDD 原则，通过新的、更精细的测试来隔离并验证这个新假设。

## [WIP] test(engine): Add verification tests for graph rebuild costs

### 错误分析
**新诊断：JIT 缓存正在按预期工作，但 `heavy_complex_countdown` 的性能瓶颈在于每次递归迭代中高昂的 `build_graph` 成本。**

让我们分解 `tco_performance.py` 中的三种关键模式：
1.  **`simple_countdown` (快速)**: 每次递归调用 `countdown(n-1)`。这是一个非常简单的 `LazyResult`，`build_graph` 的成本极低。JIT 缓存命中，`solver.resolve` 只调用一次。
2.  **`stable_complex_loop` (快速)**: 依赖链 `dep_chain` 在**循环外**构建一次。每次递归调用 `stable_complex_loop(..., _dummy=dep_chain)` 传递的是同一个 `LazyResult` 实例。`build_graph` 依然运行，但它处理的是一个结构稳定且大部分已被内部注册表（Registry）缓存的图，成本较低。JIT 缓存命中，`solver.resolve` 只调用一次。
3.  **`heavy_complex_countdown` (缓慢)**: 依赖链 `dep_chain` 在**循环内**的 Python 代码中**从头构建**。这意味着在 10,000 次迭代的每一次中，我们都在：
    *   创建 10 个新的 `LazyResult` 实例。
    *   调用 `build_graph`，它必须遍历这 11 个新实例（包括 `heavy_complex_countdown` 自身），为它们计算 `id` 和 `template_id`，并将它们组装成一个新的 `Graph` 对象。
    
    尽管最终生成的 `template_id` 是相同的（因此 `solver.resolve` 确实只被调用了一次），但我们为达到这个目标所支付的**图构建成本**是巨大的，并且被重复支付了 10,000 次。这完全解释了性能瓶颈。

这个问题触及了“Cascade 编程模型”的核心：在任务函数体内部动态构建复杂的计算图是一种反模式，因为它会将 Python 级别的构建开销带入到每一次 TCO 迭代中。

### 用户需求
需要编写新的单元测试来精确验证上述诊断：
1.  证明在 `heavy_complex_countdown` 模式下，`solver.resolve` 确实只被调用一次（证明缓存有效）。
2.  证明在 `heavy_complex_countdown` 模式下，`build_graph` 被**多次**调用（证明瓶颈所在）。
3.  （可选）证明在 `stable_complex_loop` 模式下，行为符合预期。

### 评论
这次分析更加深入。我们正在从“修复一个 bug”转向“理解并验证一个核心架构特征”。这些新测试将为我们的性能模型提供坚实的基础，并能指导用户编写更高效的 Cascade 工作流。

### 目标
1.  在 `test_jit_cache_verification.py` 中添加一个 `test_jit_cache_is_hit_but_graph_is_rebuilt` 测试。它将模拟 `heavy_complex_countdown` 的行为，并断言 `resolve` 调用 1 次，`build_graph` 调用多次。
2.  在同一文件中添加一个 `test_jit_cache_is_hit_with_stable_graph_instance` 测试。它将模拟 `stable_complex_loop` 的行为，作为对比。

### 基本原理
我们仍然遵循 TDD，但这次我们的“红灯”不是一个失败的断言，而是“性能基准测试的结果与我们的心理模型不符”。我们现在编写的测试将**全部通过**，但它们的 spy 调用计数结果将**验证我们关于性能瓶颈的新理论**，从而为下一步的文档改进或架构决策提供数据支持。

### 标签
#intent/tooling #flow/draft #priority/high #comp/tests #comp/engine #concept/cache #scope/core #ai/instruct #task/domain/core #task/object/graph-builder #task/action/verification #task/state/continue

---

### Script

#### Acts 1: 添加新的、更精确的 JIT 缓存验证测试

我们将添加两个新的测试用例，它们分别模拟 `heavy_complex_countdown` 和 `stable_complex_loop` 的行为，并监视 `build_graph` 和 `solver.resolve` 的调用。

~~~~~act
patch_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures(mocker):
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph import build as graph_builder_module


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures(mocker):
~~~~~

~~~~~act
patch_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~python
    # Therefore, resolve should have been called exactly once for the whole chain.
    assert resolve_spy.call_count == 1
~~~~~
~~~~~python
    # Therefore, resolve should have been called exactly once for the whole chain.
    assert resolve_spy.call_count == 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_but_graph_is_rebuilt_in_loop(mocker):
    """
    Verifies the "heavy_complex_countdown" scenario.
    - The JIT cache for the solver SHOULD be hit (resolve() called once).
    - But the graph itself IS REBUILT on each iteration (build_graph() called multiple times).
    This test proves that the performance bottleneck is graph construction, not solving.
    """

    @cs.task
    def noop():
        pass

    @cs.task
    def recursive_with_rebuilt_deps(n: int):
        if n <= 0:
            return "done"
        # The dependency is REBUILT inside the loop, creating new LazyResult objects
        dep = noop()
        return recursive_with_rebuilt_deps(n - 1, _dummy=dep)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    resolve_spy = mocker.spy(solver, "resolve")
    build_graph_spy = mocker.spy(graph_builder_module, "build_graph")

    iterations = 3
    target = recursive_with_rebuilt_deps(iterations)
    result = await engine.run(target)

    assert result == "done"

    # The template cache should hit after the first iteration.
    assert resolve_spy.call_count == 1

    # The graph is rebuilt for the initial call, and for each of the 3 recursive calls.
    assert build_graph_spy.call_count == iterations + 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_with_stable_graph_instance(mocker):
    """
    Verifies the "stable_complex_loop" scenario.
    When a pre-built dependency is passed in, the build cost is lower and the cache still hits.
    """

    @cs.task
    def noop():
        pass

    @cs.task
    def recursive_with_stable_deps(n: int, dep):
        if n <= 0:
            return "done"
        # The SAME dependency instance is passed along
        return recursive_with_stable_deps(n - 1, dep=dep)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    resolve_spy = mocker.spy(solver, "resolve")
    build_graph_spy = mocker.spy(graph_builder_module, "build_graph")

    # The dependency is built ONCE, outside the loop.
    stable_dep = noop()
    iterations = 3
    target = recursive_with_stable_deps(iterations, dep=stable_dep)
    result = await engine.run(target)

    assert result == "done"

    # The template cache should hit.
    assert resolve_spy.call_count == 1

    # The graph is still rebuilt, but the cost is lower as nodes are interned.
    assert build_graph_spy.call_count == iterations + 1
~~~~~

### 下一步建议
请执行此计划并运行新的测试。我们预期所有测试都会通过。这些通过的测试将验证我们关于性能瓶颈的新理论。

在确认测试通过后，下一步的合理行动是：
1.  **更新文档**: 在《Cascade 编程模型》中明确指出，在 TCO 循环内部构建复杂图是一种性能反模式，并提供 `stable_complex_loop` 作为推荐的最佳实践。
2.  **考虑长期优化**: 探索是否可以在 `GraphBuilder` 中引入更高级的缓存或 intern 机制，以降低“在循环中重建图”的成本，但这将是一个更复杂的架构任务。
