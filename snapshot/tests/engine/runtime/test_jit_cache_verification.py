import asyncio
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def static_task(n: int):
    """A task with a static structure."""
    if n <= 0:
        return "done"
    return static_task(n - 1)


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures(mocker):
    """
    Verifies that for a TCO loop with a stable structure (like simple_countdown),
    the solver is only called once, and subsequent iterations hit the JIT cache.
    """
    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    # Spy on the solver's resolve method to count its calls
    resolve_spy = mocker.spy(solver, "resolve")

    # Run a recursive task with a stable graph structure
    target = static_task(10)
    result = await engine.run(target)

    assert result == "done"
    # The solver should only be called for the first iteration.
    # All subsequent TCO iterations should hit the _plan_cache.
    assert resolve_spy.call_count == 1