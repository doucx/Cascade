import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )


@pytest.mark.asyncio
async def test_wait_is_non_blocking(engine):
    start_time = time.time()

    @cs.task
    def immediate_task():
        return "immediate"

    @cs.task
    def wrapper(a, b):
        return [a, b]

    # Both tasks are at the same stage and can run concurrently
    workflow = wrapper(cs.wait(0.1), immediate_task())

    results = await engine.run(workflow)
    duration = time.time() - start_time

    # Assert that results are correct (None for wait, 'immediate' for the other)
    # The order might vary, so we check contents
    assert None in results
    assert "immediate" in results

    # The total duration should be determined by the longest task (cs.wait),
    # not the sum of durations.
    assert 0.1 <= duration < 0.15, (
        f"Execution should be non-blocking and take ~0.1s, but took {duration:.2f}s."
    )


@pytest.mark.asyncio
async def test_wait_accepts_lazy_result(engine):
    start_time = time.time()

    @cs.task
    def get_delay():
        return 0.1

    # The delay for cs.wait is dynamically provided by get_delay
    workflow = cs.wait(get_delay())

    await engine.run(workflow)
    duration = time.time() - start_time

    assert 0.1 <= duration < 0.15, (
        f"cs.wait should have used the dynamic delay from upstream, but took {duration:.2f}s."
    )
