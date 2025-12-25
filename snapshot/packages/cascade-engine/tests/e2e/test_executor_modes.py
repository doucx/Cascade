import time
import pytest
from cascade import task


@task(mode="blocking")
def long_sync_blocking_task(duration: float) -> float:
    """A sync task representing a slow, blocking I/O operation."""
    time.sleep(duration)
    return time.time()


@task(mode="compute")
def short_sync_compute_task(duration: float) -> float:
    """A sync task representing a short but CPU-intensive operation."""
    time.sleep(duration)
    return time.time()


@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks():
    """
    Verifies that 'compute' and 'blocking' tasks run in separate thread pools
    and do not block each other.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # A short compute task (0.1s) and a long blocking task (0.2s)
    compute_lr = short_sync_compute_task(0.1)
    blocking_lr = long_sync_blocking_task(0.2)

    # If isolated, compute task finishes at T+0.1s.
    # If not isolated, compute task may have to wait for blocking task, finishing at T+0.2s or later.
    results = await engine.run([compute_lr, blocking_lr])
    compute_finish_time, blocking_finish_time = results

    # The key assertion: the short compute task must finish first.
    assert compute_finish_time < blocking_finish_time, (
        "Compute task should have finished before the blocking task, "
        "indicating parallel execution in separate pools."
    )
