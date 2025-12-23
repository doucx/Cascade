import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.spec.blueprint import TailCall
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# --- Task Definitions ---


@cs.task
def noop(_dummy=None):
    """A task that does nothing, used to force graph complexity."""
    pass


@cs.task
def simple_countdown(n: int):
    """
    A simple recursive task that will trigger the TCO fast path.
    The graph for this task is always a single node.
    """
    if n <= 0:
        return "done"
    return simple_countdown(n - 1)


@cs.task
def complex_countdown(n: int, _dummy=None):
    """
    A recursive task with a dependency, forcing a full graph build on each iteration.
    The graph for this task has two nodes (complex_countdown and noop).
    """
    if n <= 0:
        return "done"
    # The presence of `noop()` makes this a complex, multi-node graph
    return complex_countdown(n - 1, _dummy=noop())


@cs.task
def heavy_complex_countdown(n: int, _dummy=None):
    """
    A recursive task with a DEEP dependency chain, forcing a significant
    graph build and solve cost on each iteration.
    """
    if n <= 0:
        return "done"

    # Create a 10-node dependency chain to amplify the build/solve cost
    dep_chain = noop()
    for _ in range(10):
        dep_chain = noop(_dummy=dep_chain)

    return heavy_complex_countdown(n - 1, _dummy=dep_chain)


@cs.task
def stable_complex_loop(counter_box: list, _dummy=None):
    """
    A multi-node task that simulates a 'cache-friendly' TCO loop.
    It uses a mutable list (counter_box) to track iterations, so the
    arguments passed to the recursive call remain structurally IDENTICAL.

    This allows Node.id to be stable, triggering the JIT cache.
    """
    if counter_box[0] <= 0:
        return "done"

    counter_box[0] -= 1

    # We pass the SAME _dummy structure every time.
    # Note: If _dummy was rebuilt here, it would still hash the same
    # because it's built from static calls.
    return stable_complex_loop(counter_box, _dummy=_dummy)


@cs.task
def vm_countdown(n: int):
    """
    A recursive task explicitly designed for the Blueprint/VM path.
    It returns a TailCall object to trigger zero-overhead recursion.
    """
    if n <= 0:
        return "done"
    return TailCall(kwargs={"n": n - 1})


async def imperative_countdown(n: int):
    """
    A raw, imperative asyncio loop to serve as the performance ground truth.
    This has zero Cascade framework overhead.
    """
    i = n
    while i > 0:
        i -= 1
        # await asyncio.sleep(0) is essential to yield control,
        # mimicking how a long-running agent should behave.
        await asyncio.sleep(0)
    return "done"


async def run_benchmark(
    engine: Engine, target: cs.LazyResult, iterations: int, use_vm: bool = False
) -> float:
    """Runs the target and returns the execution time in seconds."""
    mode = "VM" if use_vm else "Graph/JIT"
    print(f"Running benchmark for '{target.task.name}' [{mode}]...")
    start_time = time.perf_counter()

    result = await engine.run(target, use_vm=use_vm)

    end_time = time.perf_counter()

    assert result == "done"
    return end_time - start_time


async def run_imperative_benchmark(iterations: int) -> float:
    """Runs the imperative loop and returns the execution time in seconds."""
    print("Running benchmark for 'imperative_countdown'...")
    start_time = time.perf_counter()

    result = await imperative_countdown(iterations)

    end_time = time.perf_counter()

    assert result == "done"
    return end_time - start_time


async def main():
    """Main function to run and compare benchmarks."""
    iterations = 10_000

    # Use a silent bus to avoid polluting output
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    print("--- TCO Performance Benchmark ---")
    print(f"Iterations: {iterations}\n")

    # 1. Run Optimized Path
    print("[1] Running Optimized Path (simple_countdown)...")
    optimized_target = simple_countdown(iterations)
    optimized_time = await run_benchmark(engine, optimized_target, iterations)
    optimized_tps = iterations / optimized_time
    print(f"  Finished in {optimized_time:.4f} seconds.")
    print(f"  TPS: {optimized_tps:,.2f} calls/sec\n")

    # 2. Run Heavy Un-optimized Path
    print("[2] Running Heavy Un-optimized Path (heavy_complex_countdown)...")
    unoptimized_target = heavy_complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, iterations)
    unoptimized_tps = iterations / unoptimized_time
    print(f"  Finished in {unoptimized_time:.4f} seconds.")
    print(f"  TPS: {unoptimized_tps:,.2f} calls/sec\n")

    # 2.5 Run Stable Complex Path (Cache Hit Scenario)
    print("[2.5] Running Stable Complex Path (stable_complex_loop)...")
    # Build a complex dependency chain once
    static_dep_chain = noop()
    for _ in range(10):
        static_dep_chain = noop(_dummy=static_dep_chain)

    stable_target = stable_complex_loop([iterations], _dummy=static_dep_chain)
    stable_time = await run_benchmark(engine, stable_target, iterations)
    stable_tps = iterations / stable_time
    print(f"  Finished in {stable_time:.4f} seconds.")
    print(f"  TPS: {stable_tps:,.2f} calls/sec\n")

    # 3. Run VM Path
    print("[3] Running VM Path (vm_countdown)...")
    vm_target = vm_countdown(n=iterations)
    vm_time = await run_benchmark(engine, vm_target, iterations, use_vm=True)
    vm_tps = iterations / vm_time
    print(f"  Finished in {vm_time:.4f} seconds.")
    print(f"  TPS: {vm_tps:,.2f} calls/sec\n")

    # 4. Run Imperative Ground Truth
    print("[4] Running Imperative Ground Truth (imperative_countdown)...")
    imperative_time = await run_imperative_benchmark(iterations)
    imperative_tps = iterations / imperative_time
    print(f"  Finished in {imperative_time:.4f} seconds.")
    print(f"  TPS: {imperative_tps:,.2f} calls/sec\n")

    # 5. Compare Results
    print("--- Comparison ---")
    if unoptimized_tps > 0:
        vm_vs_heavy = vm_tps / unoptimized_tps
        print(f"VM vs. Heavy (Cache Miss): {vm_vs_heavy:.2f}x faster")

    if unoptimized_tps > 0 and stable_tps > 0:
        cache_boost = stable_tps / unoptimized_tps
        print(f"Stable vs. Heavy (Cache Boost): {cache_boost:.2f}x faster")

    if optimized_tps > 0:
        vm_vs_simple = vm_tps / optimized_tps
        print(f"VM vs. Simple (Graph Caching): {vm_vs_simple:.2f}x faster")

    if imperative_tps > 0:
        overhead_ratio = imperative_tps / vm_tps
        print(f"Imperative vs. VM (Framework Overhead): {overhead_ratio:.2f}x")
        print(
            f"  (The VM path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)"
        )


if __name__ == "__main__":
    asyncio.run(main())
