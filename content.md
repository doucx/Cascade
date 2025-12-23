你说得对。

我为之前的草率结论和引入的低级错误道歉。`unittest.mock` 确实没有 `spy` 功能，那是 `pytest-mock` 插件通过 `mocker` fixture 提供的。这是一个完全可以避免的错误。

感谢你的指正。我们必须先让测试套件完全通过，才能进行下一步。

我将生成一个计划来修复这个 `ImportError`。

## [WIP] fix(tests): 修正 JIT 缓存验证测试中的 spy 导入错误

### 错误分析
-   **现象**: `pytest` 在收集测试阶段因 `ImportError: cannot import name 'spy' from 'unittest.mock'` 而崩溃。
-   **根因**: 我在 `test_jit_cache_verification.py` 中错误地从 `unittest.mock` 导入了 `spy`。正确的方式是使用 `pytest-mock` 提供的 `mocker` fixture 来创建 spy 对象。
-   **影响**: 引入了一个无法运行的新测试，阻碍了我们验证 JIT 缓存行为的进程。

### 用户需求
修复 `ImportError`，使新添加的缓存验证测试能够被 `pytest` 正确收集和执行。

### 评论
这个错误暴露了我在生成代码时的疏忽，并再次印证了在宣告胜利前进行严格验证的必要性。这是一个必须立即修复的低级错误。

### 目标
1.  修改 `test_jit_cache_verification.py`。
2.  移除错误的 `from unittest.mock import spy` 导入。
3.  将 `mocker` fixture 注入到测试函数中。
4.  使用 `mocker.spy()` 来创建 spy 对象。

### 基本原理
遵循 `pytest-mock` 插件的正确使用方法，利用其提供的 `mocker` fixture 来实现对 `solver.resolve` 方法的监视。这是在 `pytest` 环境中进行此类测试的标准和健壮的做法。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/cache-verification #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_jit_cache_verification.py`

我们将修正测试文件，使用正确的 `mocker` fixture。

~~~~~act
patch_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~python
import asyncio
from unittest.mock import spy
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def static_task(n: int):
    """A task with a static structure."""
    if n <= 0:
        return "done"
    return static_task(n - 1)


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures():
    """
    Verifies that for a TCO loop with a stable structure (like simple_countdown),
    the solver is only called once, and subsequent iterations hit the JIT cache.
    """
    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    # Spy on the solver's resolve method to count its calls
    resolve_spy = spy(solver, "resolve")

    # Run a recursive task with a stable graph structure
    target = static_task(10)
    result = await engine.run(target)

    assert result == "done"
    # The solver should only be called for the first iteration.
    # All subsequent TCO iterations should hit the _plan_cache.
    assert resolve_spy.call_count == 1
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def static_task(n: int):
    """A task with a static structure."""
    if n <= 0:
        return "done"
    return static_task(n - 1)


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures(mocker):
    """
    Verifies that for a TCO loop with a stable structure (like simple_countdown),
    the solver is only called once, and subsequent iterations hit the JIT cache.
    """
    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    # Spy on the solver's resolve method to count its calls
    resolve_spy = mocker.spy(solver, "resolve")

    # Run a recursive task with a stable graph structure
    target = static_task(10)
    result = await engine.run(target)

    assert result == "done"
    # The solver should only be called for the first iteration.
    # All subsequent TCO iterations should hit the _plan_cache.
    assert resolve_spy.call_count == 1
~~~~~

### 下一步建议
在应用此修复后，请再次运行 `pytest`。这一次，测试集合应该不会再有 `ImportError`。如果所有测试都通过，我们才能真正确认代码库处于一个稳定的状态，然后才能安全地执行之前的 `git commit` 计划。
