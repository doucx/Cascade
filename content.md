好的，这是一个非常关键的发现。

所有单元测试和集成测试都通过了，但端到端的性能基准测试却失败了，并且复现了我们最初修复的 `DependencyMissingError`。

**这强烈表明我们的测试套件中存在一个盲点。** 我们的测试没有充分覆盖“带有内部依赖的、会命中 JIT 缓存的 TCO 循环”这一特定场景。`heavy_complex_countdown` 正是这种场景，而我们的常规测试不是。

**根本原因分析**：
JIT 缓存 (`_plan_cache`) 正在按预期工作。在 `heavy_complex_countdown` 的第二次 TCO 迭代中，`GraphExecutionStrategy` 成功地从缓存中获取了 `ExecutionPlan`，从而跳过了昂贵的 `solver.resolve()` 步骤。

然而，TCO 循环的一个核心行为是在每次迭代之间**清除 `state_backend`**。这意味着，即使我们有正确的计划，我们也必须在**每次迭代中**从头到尾执行这个计划，以便为后续阶段（如 `heavy_complex_countdown` 节点本身）重新计算其依赖项（如 `noop` 链）的结果。

当前的 `DependencyMissingError` 错误表明，在缓存命中的迭代中，`noop` 链没有被执行，其结果没有被放入已清空的 `state_backend` 中，因此当 `heavy_complex_countdown` 尝试解析其 `_dummy` 参数时，依赖项的结果缺失了。这指向一个潜在的问题：`InMemoryStateBackend` 可能没有正确地实现 `clear()` 方法，导致状态在 TCO 循环之间没有被完全重置。

我将生成一个计划，首先创建一个专门捕获此回归错误的测试，然后实施修复。

## [WIP] test(runtime): 为 TCO JIT 缓存添加依赖回归测试并修复状态泄露

### 错误分析
-   **现象**: `heavy_complex_countdown` 在 TCO 循环的第二次（缓存命中）迭代中因 `DependencyMissingError` 失败。
-   **根因**: 尽管 `ExecutionPlan` 被成功缓存和复用，但在新的、已清空的 TCO 迭代上下文中，计划的前置依赖阶段没有被重新执行以填充 `state_backend`。这极有可能是因为 `InMemoryStateBackend` 缺乏一个 `clear()` 方法，导致 TCO 循环的状态清理步骤静默失败。
-   **测试盲点**: 现有测试没有覆盖“一个会命中 JIT 缓存、且包含内部数据依赖的 TCO 循环”的场景。

### 用户需求
1.  创建一个新的回归测试，以在 `pytest` 套件内可靠地复现 `tco_performance.py` 中观察到的 `DependencyMissingError`。
2.  修复 `InMemoryStateBackend`，确保 TCO 循环能够正确地重置状态，从而使缓存的计划能够成功执行。

### 评论
这个 Bug 非常微妙，因为它只在缓存、TCO 和内部依赖这三个条件同时满足时才会触发。创建一个专门的测试用例至关重要，它将成为我们未来对 `Engine` 状态管理进行任何重构时的关键安全网。

### 目标
1.  创建新测试文件 `tests/engine/runtime/test_tco_cache.py`。
2.  在新文件中实现 `test_jit_cache_handles_tco_with_dependencies` 测试用例，该用例将模拟 `heavy_complex_countdown` 的失败模式。
3.  为 `InMemoryStateBackend` 添加一个 `clear()` 方法，以确保 TCO 循环的状态重置机制能够正常工作。

### 基本原理
新的测试用例将使 Bug 的复现自动化和确定化。通过在 `InMemoryStateBackend` 中实现 `clear()` 方法，我们修复了 `GraphExecutionStrategy` 中 TCO 循环的一个隐含假设（即 `state_backend` 是可重置的），从而确保了在缓存命中的情况下，执行流程也能在干净的状态上正确地重建所有必要的依赖结果。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/regression-test #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建新的回归测试

我们将创建一个新的测试文件和测试用例，专门用于捕获这种 TCO 缓存下的依赖执行失败问题。

~~~~~act
write_file
tests/engine/runtime/test_tco_cache.py
~~~~~
~~~~~python
import asyncio
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def noop():
    """A simple dependency task."""
    return "ok"


@cs.task
def recursive_with_deps(n: int, _dep=None):
    """
    A task that recurses and has an internal dependency.
    This structure is designed to fail if the JIT cache is hit, but the
    dependencies are not re-calculated in the cleared TCO state.
    """
    if n <= 0:
        return "done"
    return recursive_with_deps(n - 1, _dep=noop())


async def test_jit_cache_handles_tco_with_dependencies():
    """
    Validates that the GraphExecutionStrategy's JIT cache correctly handles
    TCO loops where each iteration has internal dependencies.
    """
    # This engine will use the GraphExecutionStrategy with its JIT cache enabled
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # We run for a small number of iterations (e.g., 10 is enough).
    # The first iteration will populate the cache.
    # The subsequent 9 iterations will be cache hits.
    # If the bug exists, it will fail on the 2nd iteration.
    target = recursive_with_deps(10)

    result = await engine.run(target)

    assert result == "done"
~~~~~

#### Acts 2: 修复 `InMemoryStateBackend`

我们将在 `InMemoryStateBackend` 中添加 `clear()` 方法，以确保 TCO 循环可以正确重置其状态。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~python
        return self._skipped.get(node_id)
~~~~~
~~~~~python
        return self._skipped.get(node_id)

    def clear(self) -> None:
        """
        Clears all results and skip reasons. Used between TCO iterations.
        """
        self._results.clear()
        self._skipped.clear()
~~~~~

### 下一步建议
我们已经创建了回归测试并实施了修复。请再次运行 `pytest`。新的测试 `test_jit_cache_handles_tco_with_dependencies` 应该会失败（如果没有修复）然后通过（在修复后）。

如果所有测试都通过，请最后一次运行 `observatory/benchmarks/tco_performance.py`。这次它应该会成功完成，并且 `heavy_complex_countdown` 的 TPS 将会因为 JIT 缓存的正确工作而大幅提升。这将标志着路线图 v3.2 第二阶段的核心目标达成。
