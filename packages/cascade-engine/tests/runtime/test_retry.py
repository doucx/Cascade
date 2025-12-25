import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying, TaskExecutionFinished
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber


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
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

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
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

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
