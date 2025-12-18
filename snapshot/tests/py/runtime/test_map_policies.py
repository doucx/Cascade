import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying, Event
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.mark.asyncio
async def test_map_with_retry_policy():
    """
    Test that .with_retry() applied to .map() is propagated to sub-tasks.
    """
    call_counts = {}

    @cs.task
    def flaky_process(x):
        count = call_counts.get(x, 0)
        call_counts[x] = count + 1

        # Fail on first attempt for each item
        if count == 0:
            raise ValueError(f"Fail {x}")
        return x

    # Map over 3 items, expecting each to fail once then succeed
    # Total calls should be 6 (3 initial + 3 retries)
    inputs = [1, 2, 3]
    mapped = flaky_process.map(x=inputs).with_retry(max_attempts=2, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Use a dummy gather task to run everything
    @cs.task
    def gather(results):
        return results

    # We can't directly run mapped result in v1.3 because it returns a list,
    # and Engine.run expects a single LazyResult.
    # But wait, Engine.run builds a graph. If we pass a MappedLazyResult,
    # GraphBuilder handles it (node_type="map").
    # However, Engine.run returns the result of the target node.
    # For a map node, _execute_map_node returns a list of results.
    # So we CAN run mapped result directly.

    results = await engine.run(mapped)

    assert sorted(results) == [1, 2, 3]

    # Check retries occurred
    retries = spy.events_of_type(TaskRetrying)
    assert len(retries) == 3

    # Check call counts
    assert sum(call_counts.values()) == 6
    assert all(c == 2 for c in call_counts.values())


@pytest.mark.asyncio
async def test_map_with_constraints_policy():
    """
    Test that .with_constraints() applied to .map() limits concurrency of sub-tasks.
    """

    @cs.task
    async def slow_task(x):
        await asyncio.sleep(0.05)
        return time.time()

    # 4 tasks, but system has only 2 slots.
    # Should take at least 2 rounds (~0.1s total), instead of 1 round (~0.05s).
    inputs = [1, 2, 3, 4]
    mapped = slow_task.map(x=inputs).with_constraints(slots=1)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"slots": 2},  # Allow 2 concurrent tasks
    )

    start_time = time.time()
    results = await engine.run(mapped)
    duration = time.time() - start_time

    assert len(results) == 4

    # Ideally:
    # T=0: Task 1, 2 start
    # T=0.05: Task 1, 2 finish; Task 3, 4 start
    # T=0.10: Task 3, 4 finish
    # Total ~0.10s.
    # If parallel (unconstrained): ~0.05s.

    # We assert it took clearly longer than a single pass
    assert duration >= 0.09
