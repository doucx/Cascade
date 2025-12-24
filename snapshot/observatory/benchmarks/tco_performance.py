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
    iterations = 5000
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    print("--- Cascade v1.4 Performance Benchmark ---")
    print(f"Iterations: {iterations}\n")

    # Explicit Jump Loop (Simple)
    nodes_per_iter_1 = 1
    print(" Running Explicit Jump Loop (Simple)...")
    target_1 = create_explicit_loop(iterations)
    time_1 = await run_benchmark(engine, target_1)
    tps_1 = iterations / time_1
    nps_1 = tps_1 * nodes_per_iter_1
    print(f"  TPS: {tps_1:,.2f} iter/sec")
    print(f"  NPS: {nps_1:,.2f} nodes/sec\n")

    # Heavy Explicit Loop
    complexity = 20
    nodes_per_iter_2 = complexity + 1
    print(f" Running Heavy Explicit Loop (Complexity={complexity})...")
    target_2 = create_heavy_explicit_loop(iterations, complexity=complexity)
    time_2 = await run_benchmark(engine, target_2)
    tps_2 = iterations / time_2
    nps_2 = tps_2 * nodes_per_iter_2
    print(f"  TPS: {tps_2:,.2f} iter/sec")
    print(f"  NPS: {nps_2:,.2f} nodes/sec")

    # Calculate the difference in efficiency, not just raw speed
    efficiency_gain = ((nps_2 / nps_1) - 1) * 100
    print(
        f"  Throughput Gain vs Simple: {efficiency_gain:+.1f}% (Batching Efficiency)\n"
    )

    # VM Path
    print(" Running VM Path (TailCall)...")
    target_3 = vm_countdown(n=iterations)
    time_3 = await run_benchmark(engine, target_3, use_vm=True)
    tps_3 = iterations / time_3
    print(f"  TPS: {tps_3:,.2f} iter/sec\n")

    # Imperative Ground Truth
    print(" Running Imperative Ground Truth...")
    start_imp = time.perf_counter()
    await imperative_countdown(iterations)
    time_imp = time.perf_counter() - start_imp
    tps_imp = iterations / time_imp
    print(f"  TPS: {tps_imp:,.2f} iter/sec\n")

    print("--- Conclusion ---")
    print(f"Engine processes {nps_2:,.0f} nodes/sec under load (Heavy Explicit Loop).")
    print(f"VM path is {nps_1 / tps_3:.2f}x faster than Simple Explicit Jump.")
    print(
        f"Explicit Control Flow adds {(time_1 - time_imp) / iterations * 1e6:.1f} microseconds overhead per step vs raw Python loop."
    )
    print(f"Heavy Explicit Loop overhead vs VM: {((time_3 / time_2) - 1) * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
