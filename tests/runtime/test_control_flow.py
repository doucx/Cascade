import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskSkipped, TaskExecutionFinished


class EventSpy:
    def __init__(self, bus):
        self.events = []
        bus.subscribe(TaskSkipped, self.events.append)
        bus.subscribe(TaskExecutionFinished, self.events.append)


@pytest.mark.asyncio
async def test_run_if_true():
    @cs.task
    def condition():
        return True

    @cs.task
    def action():
        return "executed"

    # condition is True, should run
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = EventSpy(bus)
    engine = Engine(bus=bus)

    result = await engine.run(flow)
    assert result == "executed"

    # Check no skip events
    assert not any(isinstance(e, TaskSkipped) for e in spy.events)


@pytest.mark.asyncio
async def test_run_if_false():
    @cs.task
    def condition():
        return False

    @cs.task
    def action():
        return "executed"

    # condition is False, should skip
    flow = action().run_if(condition())

    bus = MessageBus()
    spy = EventSpy(bus)
    engine = Engine(bus=bus)

    # Engine.run returns None if the target task was skipped (as it's not in results)
    # Actually, Engine.run raises Key Error if target is missing in results dict?
    # Let's check Engine implementation: `return results[target._uuid]`
    # If target is skipped, it won't be in results.
    # We should probably handle this gracefully in Engine or expect Key Error.
    # For now, let's just assert it raises KeyError, which confirms it wasn't executed.
    # OR better: make Engine return None if target missing?
    # Current implementation will raise KeyError.

    with pytest.raises(KeyError):
        await engine.run(flow)

    # Verify Skip Event
    skip_events = [e for e in spy.events if isinstance(e, TaskSkipped)]
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

    # A is skipped
    res_a = step_a().run_if(condition())
    # B depends on A
    res_b = step_b(res_a)

    bus = MessageBus()
    spy = EventSpy(bus)
    engine = Engine(bus=bus)

    with pytest.raises(KeyError):
        await engine.run(res_b)

    skip_events = [e for e in spy.events if isinstance(e, TaskSkipped)]

    # Both A and B should be skipped
    names = sorted([e.task_name for e in skip_events])
    assert names == ["step_a", "step_b"]

    reason_a = next(e.reason for e in skip_events if e.task_name == "step_a")
    reason_b = next(e.reason for e in skip_events if e.task_name == "step_b")

    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped"
