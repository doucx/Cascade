import pytest
import asyncio
import time

from cascade.vm.executor import PhysicsExecutor

# --- Helper functions for testing ---


def add(x: int, y: int) -> int:
    return x + y


def blocking_io_simulation(duration: float) -> float:
    time.sleep(duration)
    return duration


def raises_error():
    raise ValueError("Task failed successfully")


# --- Tests ---


@pytest.mark.asyncio
async def test_executor_submit_simple_computation():
    executor = PhysicsExecutor()
    result = await executor.submit(add, (2, 3))
    assert result == 5


@pytest.mark.asyncio
async def test_executor_is_non_blocking():
    executor = PhysicsExecutor()
    sleep_duration = 0.1

    start_time = time.monotonic()

    # Create a task for the long-running job
    exec_task = asyncio.create_task(
        executor.submit(blocking_io_simulation, (sleep_duration,))
    )

    # This point should be reached almost instantly
    time_after_submit = time.monotonic()

    # Yield control to allow the task to start
    await asyncio.sleep(0)

    # Assert that the submit call itself was non-blocking
    assert (time_after_submit - start_time) < (sleep_duration / 2)

    # Now, await the actual result
    result = await exec_task
    end_time = time.monotonic()

    # Assert the task ran for the expected duration
    assert result == sleep_duration
    assert (end_time - start_time) >= sleep_duration


@pytest.mark.asyncio
async def test_executor_propagates_exceptions():
    executor = PhysicsExecutor()

    with pytest.raises(ValueError, match="Task failed successfully"):
        await executor.submit(raises_error, ())
