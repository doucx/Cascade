import asyncio
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def noop():
    """A simple dependency task."""
    return "ok"


@cs.task
def recursive_with_deps(n: int, _dep=None):
    """
    A task that recurses and has an internal dependency.
    This structure is designed to fail if the JIT cache is hit, but the
    dependencies are not re-calculated in the cleared TCO state.
    """
    if n <= 0:
        return "done"
    return recursive_with_deps(n - 1, _dep=noop())


async def test_jit_cache_handles_tco_with_dependencies():
    """
    Validates that the GraphExecutionStrategy's JIT cache correctly handles
    TCO loops where each iteration has internal dependencies.
    """
    # This engine will use the GraphExecutionStrategy with its JIT cache enabled
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # We run for a small number of iterations (e.g., 10 is enough).
    # The first iteration will populate the cache.
    # The subsequent 9 iterations will be cache hits.
    # If the bug exists, it will fail on the 2nd iteration.
    target = recursive_with_deps(10)

    result = await engine.run(target)

    assert result == "done"