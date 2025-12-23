import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_stable_structures(mocker):
    """
    Verifies that the JIT cache mechanism works when the Node structure
    (including arguments) is EXACTLY the same.

    Current Limitation: Since Node.id includes arguments, f(10) and f(9)
    are different nodes. To verify the cache works, we must use a 0-arg
    recursion that keeps the Node ID constant.
    """
    stop_flag = False

    @cs.task
    def zero_arg_recursion():
        nonlocal stop_flag
        if stop_flag:
            return "done"
        stop_flag = True
        # Recurse with NO arguments changed.
        # This produces the exact same Node.id as the current one.
        return zero_arg_recursion()

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    # Spy on the solver's resolve method to count its calls
    resolve_spy = mocker.spy(solver, "resolve")

    # 1. First iteration: stop_flag=False -> returns zero_arg_recursion()
    # 2. Second iteration: stop_flag=True -> returns "done"
    # Total TCO iterations: 2
    target = zero_arg_recursion()
    result = await engine.run(target)

    assert result == "done"

    # We expect exactly 1 call to resolve().
    # The 1st iteration calls resolve() and populates cache.
    # The 2nd iteration finds the exact same Node.id in _plan_cache and skips resolve().
    assert resolve_spy.call_count == 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_complex_stable_structures(mocker):
    """
    Verifies that JIT cache works even for multi-node graphs,
    as long as the structure is stable.
    """

    @cs.task
    def noop():
        return "ok"

    stop_flag = False

    @cs.task
    def complex_stable_recursion(_dep):
        nonlocal stop_flag
        if stop_flag:
            return "done"
        stop_flag = True

        # Crucial: We must reuse the EXACT same _dep instance (or a structurally identical one)
        # to ensure the Merkle hash remains stable.
        # Since 'noop()' produces a new LazyResult, but its structure is constant (0 args),
        # passing noop() again will produce the SAME Node.id.
        return complex_stable_recursion(_dep=noop())

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())
    resolve_spy = mocker.spy(solver, "resolve")

    # Initial call with a dependency
    target = complex_stable_recursion(_dep=noop())
    result = await engine.run(target)

    assert result == "done"
    # Even with a dependency graph, resolve should only be called once.
    assert resolve_spy.call_count == 1
