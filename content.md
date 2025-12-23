好的，遵照指示。我们严格遵循 TDD 流程。

这是一个标准的“红-绿-重构”循环的“红”阶段。我们的目标是创建一个新的测试用例，这个用例在当前的代码实现下**必须失败**。它的失败将精确地暴露出现有缓存逻辑的缺陷，为我们下一步的修复提供一个明确的目标。

## [WIP] test(engine): Add failing test for template cache with varying args

### 错误分析
基准测试 `tco_performance.py` 的结果显示，`heavy_complex_countdown` 的性能并未如预期般提升。这强烈暗示我们新实现的、基于 `template_id` 的 JIT 缓存机制存在缺陷。

根本原因很可能是：尽管我们的设计意图是让 `countdown(n)` 和 `countdown(n-1)` 共享同一个计划模板，但当前的 `GraphBuilder` 实现可能仍在 `template_id` 的计算中错误地混入了某些与 `n` 相关的实例信息，导致每次迭代都生成了**不同**的 `template_id`，从而造成缓存永远无法命中。

我们将通过编写一个专门的测试用例来验证这一假设。该测试将创建一个简单的递归任务 `countdown(n)`，并断言 `solver.resolve` 方法在整个递归链中**只被调用一次**。我们预期此测试将会失败（`resolve` 会被多次调用），从而为我们提供一个确凿的失败证据。

### 用户需求
需要一个单元测试来验证 JIT 缓存是否能对“结构相同但字面量参数不同”的递归任务（如 `countdown(n)` -> `countdown(n-1)`)正确命中，以确保性能优化的有效性。

### 评论
这是一个至关重要的测试。它将成为我们缓存归一化逻辑正确性的“试金石”。遵循 TDD 原则，先让这个测试失败，可以确保我们后续的修复是精准且有效的，同时也能防止未来的代码变更无意中破坏这个核心优化。

### 目标
1.  在 `tests/engine/runtime/test_jit_cache_verification.py` 文件中，新增一个名为 `test_jit_template_cache_is_hit_for_varying_arguments` 的测试函数。
2.  该测试将模拟一个简单的递归调用，并使用 `mocker.spy` 来监视 `solver.resolve` 的调用次数。
3.  断言 `resolve` 只被调用一次。
4.  确保此计划在执行后，测试套件会因为这个新测试的失败而失败。

### 基本原理
我们严格遵循测试驱动开发（TDD）的“红”阶段。在修复任何代码之前，我们必须先拥有一个能够稳定复现该问题的自动化测试。这个失败的测试不仅证明了问题的存在，也为我们接下来的“绿”阶段（修复代码）定义了明确的成功标准：让这个测试通过。

### 标签
#intent/tooling #flow/draft #priority/critical #comp/tests #comp/engine #concept/cache #scope/core #ai/instruct #task/domain/core #task/object/graph-builder #task/action/normalization #task/state/continue

---

### Script

#### Acts 1: 在测试套件中添加预期的失败测试

我们将向 `test_jit_cache_verification.py` 添加新的测试用例。此测试用例旨在验证具有不同参数的同一任务是否可以命中 JIT 缓存。根据我们的分析，此测试在当前的代码库中应该会失败。

~~~~~act
patch_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~python
    # Even with a dependency graph, resolve should only be called once.
    assert resolve_spy.call_count == 1
~~~~~
~~~~~python
    # Even with a dependency graph, resolve should only be called once.
    assert resolve_spy.call_count == 1


@pytest.mark.asyncio
async def test_jit_template_cache_is_hit_for_varying_arguments(mocker):
    """
    Verifies that the JIT cache hits for tasks that are structurally identical
    but have varying literal arguments, e.g., countdown(10) vs countdown(9).
    This is the core test for argument normalization via template_id.
    """

    @cs.task
    def countdown(n: int):
        if n <= 0:
            return "done"
        return countdown(n - 1)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())
    resolve_spy = mocker.spy(solver, "resolve")

    # Run a recursion chain from 2 -> 1 -> 0.
    # We expect:
    # 1. countdown(2): Cache miss, solver.resolve() is called. Plan is cached against template_id.
    # 2. countdown(1): Cache hit, solver.resolve() is NOT called.
    # 3. countdown(0): Returns "done", loop terminates.
    target = countdown(2)
    result = await engine.run(target)

    assert result == "done"

    # Therefore, resolve should have been called exactly once for the whole chain.
    assert resolve_spy.call_count == 1
~~~~~

### 下一步建议
请执行此计划。计划执行成功后，请运行 `pytest tests/engine/runtime/test_jit_cache_verification.py`。我们预期会看到一个失败的测试。在确认测试失败后，我将为您创建一个修复 `GraphBuilder` 中 `template_id` 计算逻辑的计划，以使这个新测试通过。
