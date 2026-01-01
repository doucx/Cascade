import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber


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
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

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
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
    skip_events = spy.events_of_type(TaskSkipped)
    assert len(skip_events) == 1
    assert skip_events[0].task_name == "action"
    assert skip_events[0].reason == "ConditionFalse"


@pytest.mark.asyncio
async def test_cascade_skip():
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
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(cs.DependencyMissingError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)

    # Both A and B should be skipped
    skipped_names = sorted([e.task_name for e in skip_events])
    assert skipped_names == ["step_a", "step_b"]

    reason_a = next(e.reason for e in skip_events if e.task_name == "step_a")
    reason_b = next(e.reason for e in skip_events if e.task_name == "step_b")

    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped_Data"
