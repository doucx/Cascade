import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph import build as graph_builder_module
from cascade.runtime.strategies import graph as strategies_graph_module


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


@pytest.mark.asyncio
async def test_jit_template_cache_is_hit_for_varying_arguments(mocker):
    """
    Verifies that the JIT cache hits for tasks that are structurally identical
    but have varying literal arguments, e.g., countdown(10) vs countdown(9).
    This is the core test for argument normalization via template_id.
    """

    @cs.task
    def countdown(n: int):
        if n <= 0:
            return "done"
        return countdown(n - 1)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())
    resolve_spy = mocker.spy(solver, "resolve")

    # Run a recursion chain from 2 -> 1 -> 0.
    # We expect:
    # 1. countdown(2): Cache miss, solver.resolve() is called. Plan is cached against template_id.
    # 2. countdown(1): Cache hit, solver.resolve() is NOT called.
    # 3. countdown(0): Returns "done", loop terminates.
    target = countdown(2)
    result = await engine.run(target)

    assert result == "done"

    # Therefore, resolve should have been called exactly once for the whole chain.
    assert resolve_spy.call_count == 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_but_graph_is_rebuilt_in_loop(mocker):
    """
    Verifies the "heavy_complex_countdown" scenario.
    - The JIT cache for the solver SHOULD be hit (resolve() called once).
    - But the graph itself IS REBUILT on each iteration (build_graph() called multiple times).
    This test proves that the performance bottleneck is graph construction, not solving.
    """

    @cs.task
    def noop():
        pass

    @cs.task
    def recursive_with_rebuilt_deps(n: int, _dummy=None):
        if n <= 0:
            return "done"
        # The dependency is REBUILT inside the loop, creating new LazyResult objects
        dep = noop()
        return recursive_with_rebuilt_deps(n - 1, _dummy=dep)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    resolve_spy = mocker.spy(solver, "resolve")
    # Patch where it is used, not where it is defined
    build_graph_spy = mocker.patch.object(
        strategies_graph_module, "build_graph", wraps=graph_builder_module.build_graph
    )

    iterations = 3
    target = recursive_with_rebuilt_deps(iterations)
    result = await engine.run(target)

    assert result == "done"

    # Template Cache Hits:
    # 1. recursive(3, _dummy=None) -> Template A (Resolve 1)
    # 2. recursive(2, _dummy=Lazy(noop)) -> Template B (Resolve 2)
    # 3. recursive(1, _dummy=Lazy(noop)) -> Template B (Hit)
    # 4. recursive(0, _dummy=Lazy(noop)) -> Template B (Hit)
    assert resolve_spy.call_count == 2

    # The graph is rebuilt for the initial call, and for each of the 3 recursive calls.
    assert build_graph_spy.call_count == iterations + 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_with_stable_graph_instance(mocker):
    """
    Verifies the "stable_complex_loop" scenario.
    When a pre-built dependency is passed in, the build cost is lower and the cache still hits.
    """

    @cs.task
    def noop():
        pass

    @cs.task
    def recursive_with_stable_deps(n: int, dep):
        if n <= 0:
            return "done"
        # The SAME dependency instance is passed along
        return recursive_with_stable_deps(n - 1, dep=dep)

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())

    resolve_spy = mocker.spy(solver, "resolve")
    # Patch where it is used
    build_graph_spy = mocker.patch.object(
        strategies_graph_module, "build_graph", wraps=graph_builder_module.build_graph
    )

    # The dependency is built ONCE, outside the loop.
    stable_dep = noop()
    iterations = 3
    target = recursive_with_stable_deps(iterations, dep=stable_dep)
    result = await engine.run(target)

    assert result == "done"

    # The template cache should hit.
    # Count is 2 because:
    # 1. First call passes a LazyResult (noop) -> Template A
    # 2. Second call passes the Result of noop (None) -> Template B
    # 3. Third call passes None -> Template B (Hit)
    assert resolve_spy.call_count == 2

    # The graph is still rebuilt, but the cost is lower as nodes are interned.
    assert build_graph_spy.call_count == iterations + 1
