import asyncio
import time
import pytest
from cascade import task


@task(pure=True)
def blocking_sync_task(duration: float) -> float:
    """
    A synchronous task that blocks the thread using time.sleep.
    Represents a CPU-bound or blocking I/O operation.
    """
    time.sleep(duration)
    return time.time()


@task(pure=True)
async def non_blocking_async_task(duration: float) -> float:
    """
    An asynchronous task that yields control using asyncio.sleep.
    """
    await asyncio.sleep(duration)
    return time.time()


@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
    """
    Verifies that synchronous blocking tasks are offloaded to a separate thread,
    allowing other async tasks to execute concurrently.

    FAILURE CONDITION (Current):
        Since offloading is not implemented, 'blocking_sync_task' will block the
        main event loop for 0.2s. 'non_blocking_async_task' will only start
        AFTER the sync task finishes.
        Result: async_task finishes AFTER sync_task.

    SUCCESS CONDITION (Expected):
        'blocking_sync_task' is offloaded. Both tasks start roughly at the same time.
        Since async task (0.1s) is shorter than sync task (0.2s), it should
        finish first.
        Result: async_task finishes BEFORE sync_task.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # Silent bus
    )

    # 1. Sync task takes 0.2s
    sync_result_lr = blocking_sync_task(0.2)
    # 2. Async task takes 0.1s
    async_result_lr = non_blocking_async_task(0.1)

    # If parallel: Async finishes at T+0.1, Sync at T+0.2
    # If serial: Sync finishes at T+0.2, Async starts then finishes at T+0.3

    start_time = time.time()
    results = await engine.run([sync_result_lr, async_result_lr])
    end_time = time.time()

    sync_finish_time, async_finish_time = results
    total_duration = end_time - start_time

    # Assertion 1: The async task should finish BEFORE the sync task.
    # This proves they were running in parallel.
    assert async_finish_time < sync_finish_time, (
        f"Async task finished at {async_finish_time}, which is after Sync task {sync_finish_time}. "
        "This indicates sequential execution (loop blocked)."
    )

    # Assertion 2: Total duration should be close to the longest task (0.2s),
    # not the sum of both (0.3s).
    # We allow a small buffer for overhead (0.25s).
    assert total_duration < 0.25, (
        f"Total duration {total_duration}s exceeds expected parallel time. "
        "This indicates sequential execution."
    )