import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.blueprint import TailCall

# --- Task Definitions ---


@cs.task
def noop(_dummy=None):
    """A task that does nothing, used to force graph complexity."""
    pass


@cs.task
def vm_countdown(n: int):
    """
    A recursive task for the VM path. It MUST return a TailCall object.
    """
    if n <= 0:
        return "done"
    return TailCall(kwargs={"n": n - 1})


@cs.task
def solver_countdown(n: int):
    """
    A recursive task for the old solver path. It returns a LazyResult.
    The graph for this task is always a single node and benefits from structural hashing.
    """
    if n <= 0:
        return "done"
    return solver_countdown(n - 1)


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
        # await asyncio.sleep(0) # Removed for raw speed comparison
    return "done"


async def run_benchmark(
    engine: Engine, target: cs.LazyResult, iterations: int, use_vm: bool = False
) -> float:
    """Runs the target and returns the execution time in seconds."""
    vm_str = " (VM)" if use_vm else ""
    print(f"Running benchmark for '{target.task.name}'{vm_str}...")
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
    iterations = 100_000

    # Use a silent bus to avoid polluting output
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    print("--- TCO Performance Benchmark ---")
    print(f"Iterations: {iterations:,}\n")

    # 1. Run VM Optimized Path
    print("[1] Running VM Optimized Path (vm_countdown)...")
    vm_target = vm_countdown(iterations)
    vm_time = await run_benchmark(engine, vm_target, iterations, use_vm=True)
    vm_tps = iterations / vm_time
    print(f"  Finished in {vm_time:.4f} seconds.")
    print(f"  TPS: {vm_tps:,.2f} calls/sec\n")

    # 2. Run Solver Optimized Path (Structural Hash Cache)
    print("[2] Running Solver Optimized Path (solver_countdown)...")
    solver_target = solver_countdown(iterations)
    solver_time = await run_benchmark(engine, solver_target, iterations)
    solver_tps = iterations / solver_time
    print(f"  Finished in {solver_time:.4f} seconds.")
    print(f"  TPS: {solver_tps:,.2f} calls/sec\n")

    # 3. Run Heavy Un-optimized Path
    print("[3] Running Heavy Un-optimized Path (heavy_complex_countdown)...")
    unoptimized_target = heavy_complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, iterations)
    unoptimized_tps = iterations / unoptimized_time
    print(f"  Finished in {unoptimized_time:.4f} seconds.")
    print(f"  TPS: {unoptimized_tps:,.2f} calls/sec\n")
    
    # 4. Run Imperative Ground Truth
    print("[4] Running Imperative Ground Truth (imperative_countdown)...")
    imperative_time = await run_imperative_benchmark(iterations)
    imperative_tps = iterations / imperative_time
    print(f"  Finished in {imperative_time:.4f} seconds.")
    print(f"  TPS: {imperative_tps:,.2f} calls/sec\n")

    # 5. Compare Results
    print("--- Comparison ---")
    if solver_tps > 0:
        vm_vs_solver = vm_tps / solver_tps
        print(
            f"VM vs. Solver (Optimized): {vm_vs_solver:.2f}x faster"
        )

    if unoptimized_tps > 0:
        vm_vs_heavy = vm_tps / unoptimized_tps
        print(
            f"VM vs. Solver (Heavy): {vm_vs_heavy:.2f}x faster"
        )
    
    if imperative_tps > 0:
        overhead_ratio = imperative_tps / vm_tps if vm_tps > 0 else float('inf')
        print(f"Imperative vs. VM (Framework Overhead): {overhead_ratio:.2f}x")
        print(
            f"  (The VM declarative path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)"
        )


if __name__ == "__main__":
    asyncio.run(main())
