import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict
import uuid

from .harness import InProcessConnector, MockWorkExecutor


async def set_rate_limit(connector: InProcessConnector, scope: str, rate: str):
    """Helper to publish a rate limit constraint."""
    constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
    constraint = GlobalConstraint(
        id=constraint_id,
        scope=scope,
        type="rate_limit",
        params={"rate": rate},
    )
    payload = asdict(constraint)
    topic = f"cascade/constraints/{scope.replace(':', '/')}"
    await connector.publish(topic, payload, retain=True)


@pytest.mark.asyncio
async def test_updating_rate_limit_unblocks_engine(bus_and_spy):
    """
    Regression test for the rate-limit update deadlock.
    Verifies that updating a slow rate limit to a fast one wakes up a sleeping
    engine and allows it to proceed at the new rate.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()

    # ARRANGE
    @cs.task
    def fast_task(i: int):
        return i

    # A workflow with enough tasks to clearly see the rate limit effect
    workflow = fast_task.map(i=range(5))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=connector,
    )

    # Publish a very slow rate limit *before* starting
    await set_rate_limit(connector, scope="global", rate="1/s")

    # ACT & ASSERT
    run_task = asyncio.create_task(engine.run(workflow))

    # Wait for the first task to finish, confirming the engine is running and throttled
    for _ in range(20): # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break
    
    assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
        "Engine did not start processing tasks under the initial slow rate limit."
    )

    # Now, publish a very fast rate limit. This should unblock the engine.
    await set_rate_limit(connector, scope="global", rate="100/s")

    # The engine should now wake up and finish the remaining ~4 tasks very quickly.
    # If it's deadlocked, this await will time out.
    try:
        results = await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Engine deadlocked and did not respond to the updated rate limit within the timeout.")

    # Final verification
    assert sorted(results) == [0, 1, 2, 3, 4]
    assert len(spy.events_of_type(TaskExecutionFinished)) == 5