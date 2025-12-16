好的，我们立即开始。

我将应用上一轮重构中建立的 `SpySubscriber` 模式来改进 `tests/runtime/test_control_flow.py`，以实现测试辅助工具的一致性。

## [WIP] refactor(tests): 在控制流测试中统一事件监听模式

### 摘要头
**[WIP] refactor(tests): 在控制流测试中统一事件监听模式**

### 用户需求
按照建议，将 `tests/runtime/test_control_flow.py` 中自定义的 `EventSpy` 类替换为在 `test_retry.py` 中引入的、功能更全面的 `SpySubscriber` 类，以统一整个测试套件的事件监听和断言模式。

### 评论
这是一个很好的“小重构，大影响”的例子。通过用一个标准的 `SpySubscriber` 替换临时的 `EventSpy`，我们不仅消除了重复代码，还获得了更强的能力（捕获所有事件）和更清晰的 API（`.events_of_type()` 辅助方法）。这使得测试代码更易于阅读和维护，并进一步巩固了我们的“Dogfooding”测试策略。

### 目标
1.  在 `tests/runtime/test_control_flow.py` 文件中，移除 `EventSpy` 类的定义。
2.  引入 `SpySubscriber` 类的定义。
3.  更新所有测试用例，使用 `SpySubscriber` 实例化事件监听器。
4.  修改断言逻辑，使用 `spy.events_of_type(TaskSkipped)` 来获取和验证事件，使代码更简洁、更具可读性。

### 基本原理
在测试套件中保持辅助工具和模式的一致性，可以显著降低开发者的认知负荷。当所有测试都使用相同的方式来监听和断言事件时，理解和编写新测试的速度会大大加快。此举旨在将 `SpySubscriber` 确立为我们测试 `Engine` 行为的标准工具。

### 标签
#intent/refine #flow/ready #priority/low #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/dogfooding #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `test_control_flow.py`

我们将使用 `write_file` 覆盖此文件，引入 `SpySubscriber` 并更新所有测试用例以使用新的模式。

~~~~~act
write_file
tests/runtime/test_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped, TaskExecutionFinished


class SpySubscriber:
    """A standard test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.mark.asyncio
async def test_run_if_true():
    @cs.task
    def condition():
        return True

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(flow)
    assert result == "executed"

    # Check no skip events were fired
    assert not spy.events_of_type(TaskSkipped)


@pytest.mark.asyncio
async def test_run_if_false():
    @cs.task
    def condition():
        return False

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(KeyError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
    skip_events = spy.events_of_type(TaskSkipped)
    assert len(skip_events) == 1
    assert skip_events[0].task_name == "action"
    assert skip_events[0].reason == "ConditionFalse"


@pytest.mark.asyncio
async def test_cascade_skip():
    """
    Test that if A is skipped, B (which depends on A) is also skipped.
    """

    @cs.task
    def condition():
        return False

    @cs.task
    def step_a():
        return "A"

    @cs.task
    def step_b(val):
        return f"B got {val}"

    res_a = step_a().run_if(condition())
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(KeyError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)

    # Both A and B should be skipped
    skipped_names = sorted([e.task_name for e in skip_events])
    assert skipped_names == ["step_a", "step_b"]

    reason_a = next(e.reason for e in skip_events if e.task_name == "step_a")
    reason_b = next(e.reason for e in skip_events if e.task_name == "step_b")

    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped"
~~~~~

### 下一步建议
太好了。我们已经成功地将两个关键的运行时测试（`retry` 和 `control_flow`）迁移到了新的、基于事件的“Dogfooding”测试模式。

这些改进现在是时候作为一个逻辑单元提交了。我建议下一步生成一个 `[COMMIT]` 计划，将这两次测试重构合并到一个原子提交中，以清晰地记录我们对测试质量的提升。
