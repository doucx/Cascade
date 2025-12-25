import pytest

from cascade import task, Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySolver


# Define a simple task for testing
@task
def add(a: int, b: int) -> int:
    return a + b


@pytest.fixture
def engine_with_spy_solver():
    """Provides an Engine with a solver that spies on `resolve` calls."""
    # The spy wraps a real solver to ensure the test can actually run
    spy_solver = SpySolver(NativeSolver())

    engine = Engine(
        solver=spy_solver,
        executor=LocalExecutor(),
        bus=MessageBus(),  # A silent bus for clean test output
    )
    # Return the engine and the mock object for making assertions
    return engine, spy_solver.resolve


@pytest.mark.asyncio
async def test_engine_reuses_plan_for_structurally_identical_graphs(
    engine_with_spy_solver,
):
    """
    Tests that the Engine's JIT plan cache is effective.

    It runs two workflows that are structurally identical but have different
    literal parameters. The solver should only be called once, for the first
    workflow, and the plan should be reused for the second.
    """
    engine, mock_resolve = engine_with_spy_solver

    # Define two structurally identical workflows with different literals
    workflow_a = add(1, 2)
    workflow_b = add(3, 4)

    # Run both workflows
    result_a = await engine.run(workflow_a)
    assert result_a == 3

    result_b = await engine.run(workflow_b)
    assert result_b == 7

    # Assert that the expensive solver was only called once
    mock_resolve.assert_called_once()
