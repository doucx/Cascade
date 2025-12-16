你的分析非常深刻。现在确实是应用《自我测试》愿景的最佳时机。

我们刚刚完成了对测试套件的结构性重构，使其与源码的“洋葱架构”保持一致。这为我们提供了一个清晰、分层的画布，可以在其上绘制更健壮、更具表现力的测试用例。直接在这些新的、职责明确的测试模块中引入“Dogfooding”原则，是巩固这次重构成果并提升测试质量的完美下一步。

我将以 `tests/runtime/test_retry.py` 为例，因为它完美地展示了如何从测试**内部实现细节**（一个 `nonlocal` 计数器）转向测试**可观测的公共行为**（`Engine` 发出的事件）。这完全符合 `d3-principle-python-testing-mock-intent` 的核心思想：验证意图，而非实现。

我将生成一个计划来执行这次重构。

## [WIP] refactor(tests): 应用'Dogfooding'原则重构重试测试

### 用户需求
根据《自我测试》愿景分析，将至少一个现有的测试用例重构为使用 Cascade 自身的声明式 API 和 `MessageBus` 事件流进行断言的模式，以提升测试的健壮性和表达力。

### 评论
这是一个关键的改进。当前的 `test_retry.py` 依赖一个 `nonlocal call_count` 变量来验证重试逻辑。这种方法很脆弱，因为它测试的是测试函数闭包的内部状态，而不是 `Engine` 的行为。

通过重构，我们将转而断言 `MessageBus` 上是否出现了预期的 `TaskRetrying` 和 `TaskExecutionFinished` 事件。这有两个核心优势：
1.  **测试公共契约**: 我们测试的是 `Engine` 公开的、可观测的事件输出，这是其行为的“公共 API”，而不是其内部实现。
2.  **表达力更强**: 测试用例本身（“断言收到了两个重试事件和一个成功事件”）比（“断言计数器等于3”）更能清晰地描述被测功能的预期行为。

### 目标
1.  重构 `tests/runtime/test_retry.py` 中的 `test_retry_success_after_failure` 和 `test_retry_exhausted_failure` 测试用例。
2.  移除对 `nonlocal call_count` 的依赖。
3.  在测试中引入 `MessageBus` 和一个事件收集器（`SpySubscriber`）。
4.  将测试断言改为检查捕获到的事件流，验证重试次数、最终状态等是否符合预期。
5.  由于 `Engine.run` 是一个 `async` 方法，需要将测试函数标记为 `async def` 并使用 `pytest.mark.asyncio`。

### 基本原理
此重构遵循了“吃自己的狗粮”（Dogfooding）和“测试意图而非实现”的核心原则。通过让测试用例成为 `Engine` 事件总线的客户端，我们确保了测试与 `Engine` 的实际用户（如日志系统、UI）处于同等地位。这使得测试用例对 `Engine` 内部逻辑的重构具有更强的免疫力，只要事件契约保持不变，测试就能持续有效。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #comp/runtime #scope/dx #ai/brainstorm #task/domain/testing #task/object/dogfooding #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `test_retry.py` 以使用事件总线断言

我们将完全重写 `tests/runtime/test_retry.py` 文件，引入 `MessageBus` 和 `Engine` 的直接实例化，并根据捕获的事件进行断言。

~~~~~act
write_file
tests/runtime/test_retry.py
~~~~~
~~~~~python
import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskRetrying, TaskExecutionFinished


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.mark.asyncio
async def test_retry_success_after_failure():
    """
    Tests that a task retries based on events and eventually succeeds.
    """
    call_count = 0

    @cs.task
    def flaky_task():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Fail!")
        return "Success"

    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(task_with_retry)

    assert result == "Success"

    # Assert based on events, not call_count
    retry_events = spy.events_of_type(TaskRetrying)
    assert len(retry_events) == 2  # Failed twice, retried twice
    assert retry_events[0].attempt == 1
    assert retry_events[1].attempt == 2

    finished_events = spy.events_of_type(TaskExecutionFinished)
    assert len(finished_events) == 1
    assert finished_events[0].status == "Succeeded"


@pytest.mark.asyncio
async def test_retry_exhausted_failure():
    """
    Tests that a task fails after exhausting all retries, based on events.
    """
    call_count = 0

    @cs.task
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fail")

    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Always fail"):
        await engine.run(task_with_retry)

    # Assert based on events
    retry_events = spy.events_of_type(TaskRetrying)
    assert len(retry_events) == 2  # Retried twice
    assert retry_events[0].attempt == 1
    assert retry_events[1].attempt == 2

    finished_events = spy.events_of_type(TaskExecutionFinished)
    assert len(finished_events) == 1
    assert finished_events[0].status == "Failed"
    assert "ValueError: Always fail" in finished_events[0].error
    
    # We can still infer call count from events, which is more robust
    assert len(retry_events) + 1 == call_count
~~~~~

### 下一步建议
我们已经成功地将“Dogfooding”原则应用于重试逻辑的测试中。

我建议下一步将此模式推广到其他适合的运行时测试中，特别是 `tests/runtime/test_control_flow.py`，用 `SpySubscriber` 替换其现有的 `EventSpy`，以保持一致性。

完成这一轮测试质量提升后，我们就可以满怀信心地开始开发下一个核心功能：**`cs.visualize`**。
