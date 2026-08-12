import asyncio
import time

import cascade.sdk as cs
import pytest
from cascade.bus.events import TaskRetrying
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySubscriber


@pytest.mark.asyncio
async def test_map_with_retry_policy(engine_factory):
    call_counts = {}

    @cs.task
    def flaky_process(x):
        count = call_counts.get(x, 0)
        call_counts[x] = count + 1

        # Fail on first attempt for each item
        if count == 0:
            raise ValueError(f"Fail {x}")
        return x

    inputs = [1, 2, 3]
    mapped = flaky_process.map(x=inputs).with_retry(max_attempts=2, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    results = await engine.run(mapped)

    assert sorted(results) == [1, 2, 3]

    # Check retries occurred
    retries = spy.events_of_type(TaskRetrying)
    assert len(retries) == 3

    # Check call counts
    assert sum(call_counts.values()) == 6
    assert all(c == 2 for c in call_counts.values())


@pytest.mark.asyncio
async def test_map_with_constraints_policy(engine_factory):
    @cs.task
    async def slow_task(x):
        await asyncio.sleep(0.05)
        return time.time()

    # 4 tasks, but system has only 2 slots.
    inputs = [1, 2, 3, 4]
    mapped = slow_task.map(x=inputs).with_constraints(slots=1)

    engine = engine_factory(
        system_resources={"slots": 2},  # Allow 2 concurrent tasks
    )

    start_time = time.time()
    results = await engine.run(mapped)
    duration = time.time() - start_time

    assert len(results) == 4

    # We assert it took clearly longer than a single pass
    assert duration >= 0.09
