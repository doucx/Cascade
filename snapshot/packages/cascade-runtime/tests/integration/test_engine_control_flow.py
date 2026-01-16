import pytest
import cascade.sdk as cs
from cascade.runtime import EventBus
from cascade.bus.events import TaskSkipped
from cascade.execution.graph.errors import DependencyMissingError
from cascade.test_utils.helpers import SpySubscriber


@pytest.mark.asyncio
async def test_run_if_true(engine_factory):
    @cs.task
    def condition():
        return True

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    result = await engine.run(flow)
    assert result == "executed"

    # Check no skip events were fired
    assert not spy.events_of_type(TaskSkipped)


@pytest.mark.asyncio
async def test_run_if_false(engine_factory):
    @cs.task
    def condition():
        return False

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
    skip_events = spy.events_of_type(TaskSkipped)
    assert len(skip_events) == 1
    assert skip_events[0].task_name == "action"
    assert skip_events[0].reason == "ConditionFalse"


@pytest.mark.asyncio
async def test_cascade_skip(engine_factory):
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

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)

    # Both A and B should be skipped
    skipped_names = sorted([e.task_name for e in skip_events])
    assert skipped_names == ["step_a", "step_b"]

    reason_a = next(e.reason for e in skip_events if e.task_name == "step_a")
    reason_b = next(e.reason for e in skip_events if e.task_name == "step_b")

    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped_Data"