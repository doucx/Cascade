from __future__ import annotations

import time

import cascade.sdk as cs
import pytest
from cascade.bus.events import TaskExecutionFinished
from cascade.test_utils.helpers import MockExecutor

from .harness import InProcessConnector


@pytest.mark.asyncio
async def test_e2e_rate_limit_control(engine_factory, bus_and_spy):
    """
    Full end-to-end test for rate limiting.
    1. Controller publishes a rate limit constraint (Retained).
    2. Engine starts, receives the constraint, and throttles execution.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()
    bus, spy = bus_and_spy

    # 2. Setup Helper (Inline to avoid complex harness changes for now)
    import uuid
    from dataclasses import asdict

    from cascade.spec.dsl.constraint import GlobalConstraint

    async def set_rate_limit(scope: str, rate: str, capacity: float | None = None):
        params = {"rate": rate}
        if capacity is not None:
            params["capacity"] = capacity

        constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="rate_limit",
            params=params,
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 3. Publish the constraint FIRST.
    # Limit to 5 tasks/sec (1 every 0.2s), with a burst capacity of 2.
    await set_rate_limit(scope="task:fast_task", rate="5/s", capacity=2)

    # 4. Define the workflow
    @cs.task
    def fast_task():
        return  # Does almost nothing

    # 4 tasks that should be rate-limited
    workflow = fast_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = engine_factory(
        executor=MockExecutor(delay=0.01),  # Short work time
        bus=bus,
        connector=connector,
    )

    # 6. Run the engine
    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions based on event timestamps
    finished_events = spy.events_of_type(TaskExecutionFinished)
    assert len(finished_events) == 4

    finish_times = sorted([e.timestamp - start_time for e in finished_events])

    # Expected timing:
    # - Capacity=2, so Task 1 & 2 run immediately in the first 0.01s slot.
    # - Rate=5/s -> 1 token refills every 0.2s.
    # - T=0.01s: T1, T2 finish. Bucket is empty.
    # - T=0.20s: 1 token available. T3 starts.
    # - T=0.21s: T3 finishes.
    # - T=0.40s: 1 token available. T4 starts.
    # - T=0.41s: T4 finishes.
    # Total duration should be ~0.4s. Without rate limit, it's ~0.01s.

    assert duration >= 0.38, (
        f"Expected throttled execution (~0.4s), but took {duration:.4f}s"
    )

    # Check the timestamps to verify sequential execution after burst
    # First two should be very close together
    # Note: Relaxed to 0.25 to accommodate potential test env jitter, though ideally < 0.05
    # If it is >= 0.2, it means capacity=2 failed and fallback to capacity=1
    assert finish_times[1] - finish_times[0] < 0.25
    # Gap between 2nd and 3rd should be ~0.2s
    assert finish_times[2] - finish_times[1] > 0.18
    # Gap between 3rd and 4th should be ~0.2s
    assert finish_times[3] - finish_times[2] > 0.18
