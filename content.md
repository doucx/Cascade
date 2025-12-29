你说得完全正确。

在性能基准测试中，同步的 `@cs.task` 会被 `LocalExecutor` 通过 `asyncio.to_thread` 包装，这会引入显著的线程切换开销，从而掩盖了引擎本身的执行效率。将这些纯计算、非阻塞的任务改为异步（`async def`），可以让它们直接在事件循环上以零开销的方式执行，从而得到更精确的性能数据。

我将生成一个计划来修改 `observatory/benchmarks/tco_performance.py` 文件。

## [WIP] perf: 将基准测试任务转换为异步以避免线程开销

### 用户需求
将 `tco_performance.py` 基准测试脚本中的所有 `@cs.task` 定义的函数修改为异步函数（`async def`），以消除 `to_thread` 带来的性能影响。

### 评论
这是一个非常准确的优化建议。对于性能基准测试来说，确保测量的是核心逻辑的开销至关重要。将这些任务转换为异步是消除不相关噪声、获取真实性能数据的正确方法。

### 目标
1.  修改 `observatory/benchmarks/tco_performance.py` 文件。
2.  将 `noop`, `explicit_countdown_step`, `heavy_step`, 和 `vm_countdown` 四个任务的定义从 `def` 改为 `async def`。

### 基本原理
由于修改点分散在文件的多个位置，根据协议 (`d2-skill-quipu-decide-write-patch-D2`)，最稳定和清晰的方法是使用 `write_file` 操作，提供带有 `async` 关键字的完整文件内容。这将确保修改的原子性和正确性。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/benchmark-script #task/action/optimization #task/state/begin

---
### Script

#### Acts 1: 更新基准测试脚本

我们将使用 `write_file` 来更新 `tco_performance.py`，将所有 `@cs.task` 装饰的函数转换为异步定义。

~~~~~act
write_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.spec.blueprint import TailCall
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# --- Task Definitions ---


@cs.task
async def noop(_dummy=None):
    """A task that does nothing, used to force graph complexity."""
    return "done"


# 1. Explicit Loop (The new standard)
@cs.task
async def explicit_countdown_step(n: int):
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
async def heavy_step(n: int, _structure=None):
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
async def vm_countdown(n: int):
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
~~~~~
