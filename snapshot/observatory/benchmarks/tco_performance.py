import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# --- Task Definitions ---

@cs.task
def noop():
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


async def run_benchmark(engine: Engine, target: cs.LazyResult, iterations: int) -> float:
    """Runs the target and returns the execution time in seconds."""
    print(f"Running benchmark for '{target.task.name}'...")
    start_time = time.perf_counter()
    
    result = await engine.run(target)
    
    end_time = time.perf_counter()
    
    assert result == "done"
    return end_time - start_time


async def main():
    """Main function to run and compare benchmarks."""
    iterations = 10_000
    
    # Use a silent bus to avoid polluting output
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus()
    )

    print("--- TCO Performance Benchmark ---")
    print(f"Iterations: {iterations}\n")

    # 1. Run Optimized Path
    print("[1] Running Optimized Path (simple_countdown)...")
    optimized_target = simple_countdown(iterations)
    optimized_time = await run_benchmark(engine, optimized_target, iterations)
    optimized_tps = iterations / optimized_time
    print(f"  Finished in {optimized_time:.4f} seconds.")
    print(f"  TPS: {optimized_tps:,.2f} calls/sec\n")

    # 2. Run Un-optimized Path
    print("[2] Running Un-optimized Path (complex_countdown)...")
    unoptimized_target = complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, iterations)
    unoptimized_tps = iterations / unoptimized_time
    print(f"  Finished in {unoptimized_time:.4f} seconds.")
    print(f"  TPS: {unoptimized_tps:,.2f} calls/sec\n")
    
    # 3. Compare Results
    if unoptimized_tps > 0:
        improvement = optimized_tps / unoptimized_tps
        print("--- Comparison ---")
        print(f"Performance Improvement: {improvement:.2f}x")


if __name__ == "__main__":
    asyncio.run(main())