好的，我们正式启动 **里程碑 1.3**：实现时间感知原语 `cs.wait`。

遵循 TDD 流程，我将首先创建测试套件。由于 `cascade-py/src/cascade/providers/time.py` 文件和 `cs.wait` 提供者都还不存在，因此访问 `cs.wait` 会立即导致 `AttributeError`，使我们进入 **Red** 阶段。

## [WIP] test(providers): 为时间原语 cs.wait 添加 TDD 测试

### 用户需求
为“萤火计划” Milestone 1.3 的 `cs.wait` 原子任务创建 TDD 测试套件。
测试需覆盖以下核心功能：
1.  **非阻塞节拍**: 验证 `cs.wait` 是一个非阻塞的异步操作，它会暂停当前任务的执行，但不会阻塞整个 `asyncio` 事件循环。
2.  **动态参数化**: 验证 `cs.wait` 的延迟时间可以接受来自上游任务的 `LazyResult` 作为输入。

### 评论
`cs.wait` 是赋予工作流“自律”能力的基础。它让 Agent 能够控制自身的行为频率和脉冲节拍，是构建响应式和周期性行为的关键“积木”。这两个测试用例精确地定义了它的核心契约。

### 目标
创建 `tests/py/providers/test_time_provider.py` 文件，并包含 `test_wait_is_non_blocking` 和 `test_wait_accepts_lazy_result` 两个预期失败的测试用例。

### 基本原理
我们首先编写测试来定义 `cs.wait` 必须满足的行为规范。
*   `test_wait_is_non_blocking`: 通过并行运行一个 `cs.wait(0.1)` 任务和一个立即完成的任务来验证。如果 `cs.wait` 是阻塞的，总耗时将大于 0.1 秒；如果非阻塞，总耗时将约等于 0.1 秒。
*   `test_wait_accepts_lazy_result`: 定义一个返回数字的上游任务，并将其 `LazyResult` 传递给 `cs.wait`。通过测量执行时间，验证 `cs.wait` 使用了动态生成的延迟值。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/core #concept/time #scope/api #ai/instruct #task/domain/providers #task/object/wait-primitive #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建 `cs.wait` 的测试套件

我们将创建新的测试文件 `tests/py/providers/test_time_provider.py`。

~~~~~act
write_file
tests/py/providers/test_time_provider.py
~~~~~
~~~~~python
import asyncio
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.fixture
def engine():
    """Provides a default engine instance."""
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )


@pytest.mark.asyncio
async def test_wait_is_non_blocking(engine):
    """
    Test Case 6 (From Firefly Plan): Non-blocking Tick.

    Verifies that cs.wait(t) pauses for approximately t seconds, and does so
    without blocking the execution of other concurrent tasks.
    """
    start_time = time.time()

    @cs.task
    def immediate_task():
        return "immediate"

    @cs.task
    def wrapper(a, b):
        return [a, b]

    # Both tasks are at the same stage and can run concurrently
    workflow = wrapper(cs.wait(0.1), immediate_task())

    results = await engine.run(workflow)
    duration = time.time() - start_time

    # Assert that results are correct (None for wait, 'immediate' for the other)
    # The order might vary, so we check contents
    assert None in results
    assert "immediate" in results

    # The total duration should be determined by the longest task (cs.wait),
    # not the sum of durations.
    assert 0.1 <= duration < 0.15, (
        f"Execution should be non-blocking and take ~0.1s, but took {duration:.2f}s."
    )


@pytest.mark.asyncio
async def test_wait_accepts_lazy_result(engine):
    """
    Test Case 7 (From Firefly Plan): Dynamic Parameterized Time.

    Verifies that the delay argument of cs.wait can be a LazyResult
    from an upstream task.
    """
    start_time = time.time()

    @cs.task
    def get_delay():
        return 0.1

    # The delay for cs.wait is dynamically provided by get_delay
    workflow = cs.wait(get_delay())

    await engine.run(workflow)
    duration = time.time() - start_time

    assert 0.1 <= duration < 0.15, (
        f"cs.wait should have used the dynamic delay from upstream, but took {duration:.2f}s."
    )

~~~~~

### 下一步建议
运行测试。由于 `cs.wait` 不存在，测试将因 `AttributeError` 而失败。确认失败后，我将生成实现 `cascade.providers.time` 模块和注册新提供者的计划，使测试通过。
