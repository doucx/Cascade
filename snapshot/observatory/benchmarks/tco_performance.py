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
    return "done"


# 1. Explicit Loop (The new standard)
@cs.task
def explicit_countdown_step(n: int):
    if n <= 0:
        return cs.Jump(target_key="exit", data="done")
    return cs.Jump(target_key="loop", data=n - 1)


def create_explicit_loop(n: int):
    # This represents the new way to build loops in Cascade
    # It creates a static graph with a jump back to the target
    step = explicit_countdown_step(n)

    selector = cs.select_jump({"loop": step, "exit": None})

    cs.bind(step, selector)
    return step


# 2. Heavy Explicit Loop (Testing Blueprint Cache Efficiency)
@cs.task
def heavy_step(n: int, _structure=None):
    if n <= 0:
        return cs.Jump(target_key="exit", data="done")
    return cs.Jump(target_key="loop", data=n - 1)


def create_heavy_explicit_loop(n: int, complexity: int = 20):
    # Build a massive static dependency tree that remains stable during the loop
    dep_chain = noop()
    for _ in range(complexity):
        dep_chain = noop(_dummy=dep_chain)

    step = heavy_step(n, _structure=dep_chain)
    selector = cs.select_jump({"loop": step, "exit": None})
    cs.bind(step, selector)
    return step


# 3. VM Countdown (TailCall)
@cs.task
def vm_countdown(n: int):
    if n <= 0:
        return "done"
    return TailCall(kwargs={"n": n - 1})


async def imperative_countdown(n: int):
    """Ground truth: Raw Python loop."""
    i = n
    while i > 0:
        i -= 1
        await asyncio.sleep(0)
    return "done"


async def run_benchmark(
    engine: Engine, target: cs.LazyResult, use_vm: bool = False
) -> float:
    """Runs the target and returns the execution time in seconds."""
    start_time = time.perf_counter()
    result = await engine.run(target, use_vm=use_vm)
    end_time = time.perf_counter()

    assert result == "done"
    return end_time - start_time


async def main():
    iterations = 5_000  # Reasonable count for comparison
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    print("--- Cascade v1.4 Performance Benchmark ---")
    print(f"Iterations: {iterations}\n")

    # [1] Explicit Jump (Graph Strategy)
    # This tests the "Blueprint Cache Hit" speed
    print("[1] Running Explicit Jump Loop (Blueprint Cache)...")
    target_1 = create_explicit_loop(iterations)
    time_1 = await run_benchmark(engine, target_1)
    print(f"  TPS: {iterations / time_1:,.2f} calls/sec\n")

    # [2] Heavy Explicit Jump
    # This verifies that solve cost is ZERO even for complex graphs after iteration 1
    print("[2] Running Heavy Explicit Loop (Complexity=20)...")
    target_2 = create_heavy_explicit_loop(iterations, complexity=20)
    time_2 = await run_benchmark(engine, target_2)
    print(f"  TPS: {iterations / time_2:,.2f} calls/sec")
    print(f"  Penalty for complexity: {((time_2/time_1)-1)*100:.1f}%\n")

    # [3] VM Path
    print("[3] Running VM Path (TailCall)...")
    target_3 = vm_countdown(n=iterations)
    time_3 = await run_benchmark(engine, target_3, use_vm=True)
    print(f"  TPS: {iterations / time_3:,.2f} calls/sec\n")

    # [4] Imperative Ground Truth
    print("[4] Running Imperative Ground Truth...")
    start_imp = time.perf_counter()
    await imperative_countdown(iterations)
    time_imp = time.perf_counter() - start_imp
    print(f"  TPS: {iterations / time_imp:,.2f} calls/sec\n")

    # Summary
    print("--- Summary ---")
    print(f"VM path is {time_1 / time_3:.2f}x faster than Graph Jump.")
    print(f"Graph Jump is {time_imp / time_1:.2f}x slower than native loop.")


if __name__ == "__main__":
    asyncio.run(main())