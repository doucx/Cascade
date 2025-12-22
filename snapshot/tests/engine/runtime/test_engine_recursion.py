import sys
import pytest
from typing import Generator
from unittest.mock import MagicMock, call

import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.spec.resource import resource, inject


# --- Fixtures ---


@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )


# --- Test Cases ---


@pytest.mark.asyncio
async def test_deep_recursion_tco(engine):
    """
    Test Case 4 (From Firefly Plan): Deep Recursion Pressure Test.

    Verifies that the engine can handle a recursion depth significantly larger
    than the Python recursion limit by unrolling the execution loop (TCO).

    If the engine recursively calls `execute` for the returned LazyResult,
    this test will fail with RecursionError.
    If the engine returns the LazyResult without executing it,
    this test will fail assertion on the final result.
    """
    # Set a recursion depth that is definitely unsafe for standard recursion
    # Python's default is usually 1000.
    RECURSION_DEPTH = 1500

    # Increase system limit slightly just to be sure we are testing logic,
    # not hitting a tight default, but 1500 is usually enough to crash naive recursion.
    sys.setrecursionlimit(2000)

    @cs.task
    def countdown(n: int):
        if n <= 0:
            return "Done"
        return countdown(n - 1)

    # Execution
    # We expect the engine to automatically execute the returned LazyResult
    # until it hits a non-LazyResult value.
    try:
        result = await engine.run(countdown(RECURSION_DEPTH))
    except RecursionError:
        pytest.fail("Engine hit RecursionError. It likely does not implement TCO.")

    # Assertions
    assert result == "Done", (
        f"Expected 'Done', got {result}. Did the engine stop early?"
    )


@pytest.mark.asyncio
async def test_resource_release_in_recursion(engine):
    """
    Test Case 5 (From Firefly Plan): Resource Smooth Release.

    Verifies that resources used in one step of a recursive chain are released
    *before* or *as* the next step begins, rather than accumulating until the end.
    This is critical for long-running agents to avoid resource leaks.
    """

    mock_tracker = MagicMock()

    @resource(
        name="scope_resource", scope="task"
    )  # Note: scope='task' implies release after task
    def tracked_resource() -> Generator[str, None, None]:
        mock_tracker.setup()
        yield "active"
        mock_tracker.teardown()

    engine.register(tracked_resource)

    @cs.task
    def step_two(res=inject("scope_resource")):
        mock_tracker.step_two_run()
        return "Finish"

    @cs.task
    def step_one(res=inject("scope_resource")):
        mock_tracker.step_one_run()
        # Return the next step (LazyResult)
        return step_two()

    # Execution
    await engine.run(step_one())

    # Analysis of call order
    # The expected behavior for TCO / Agent loop is:
    # 1. step_one acquires resource
    # 2. step_one runs
    # 3. step_one finishes -> **resource should be released here** (context switch)
    # 4. step_two acquires resource
    # 5. step_two runs
    # 6. step_two finishes -> resource released

    # If the engine holds the context of step_one open while waiting for the result
    # of step_two (recursive behavior), the teardown of step_one won't happen
    # until step_two finishes.

    calls = mock_tracker.mock_calls

    # Let's look for the sequence
    # Expected: setup -> run1 -> teardown -> setup -> run2 -> teardown
    # Or at least: run1 -> teardown -> run2

    try:
        calls.index(call.step_one_run())
        idx_run2 = calls.index(call.step_two_run())
    except ValueError:
        pytest.fail("Tasks did not run as expected.")

    # Find teardowns
    teardown_indices = [i for i, c in enumerate(calls) if c == call.teardown()]

    assert len(teardown_indices) >= 2, (
        "Resource should be torn down twice (once for each task)."
    )

    first_teardown = teardown_indices[0]

    # Critical Assertion: The first teardown must happen BEFORE step_two starts.
    # This proves that step_one's context was closed before step_two's context was opened.
    if first_teardown > idx_run2:
        pytest.fail(
            "Resource leak detected: step_one's resource was not released before step_two started. "
            "The engine is likely holding the previous frame open."
        )
