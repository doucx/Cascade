好的，我们现在将 `tco_performance.py` 更新为使用新的 VM 路径，这将作为我们新架构性能的最终验证。

## [WIP] test(perf): Update TCO benchmark to use VM execution path

### 摘要头
`# [WIP] test(perf): Update TCO benchmark to use VM execution path`

### 用户需求
1.  修改 `tco_performance.py` 基准测试脚本。
2.  将 `simple_countdown` 任务改为返回 `TailCall`，以适配 VM 的 TCO 机制。
3.  在 `run_benchmark` 函数中调用 `engine.run(..., use_vm=True)` 来启用新的执行路径。
4.  脚本的其余部分（非优化路径和命令式路径）保持不变，作为对照组。

### 评论
这是我们工作的“真理时刻”。此基准测试将直接量化 Blueprint/VM 架构带来的性能提升。我们的目标是让 `simple_countdown`（VM 路径）的性能与 `imperative_countdown`（原生 Python 循环）的性能处于同一数量级，并显著超越 `heavy_complex_countdown`（旧的图构建路径）。

### 目标
通过修改后的基准测试，证明 VM 路径的性能优势。

### 基本原理
通过将 `simple_countdown` 的递归调用改为返回 `TailCall`，并用 `use_vm=True` 运行，我们指示 `Engine` 使用我们刚刚构建的全新 AOT/VM 路径。这将完全绕过 `build_graph` 和 `solver` 的开销，实现接近命令式循环的性能。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/performance-benchmark #task/action/update #task/state/continue

---

### Script

#### Acts 1: 更新 `tco_performance.py`

我们将 `simple_countdown` 任务的递归调用从返回 `LazyResult` 改为返回 `TailCall`，并更新 `run_benchmark` 以启用 VM。

~~~~~act
write_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.runtime.blueprint import TailCall # NEW
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
    A simple recursive task that will trigger the TCO fast path via the VM.
    It returns a TailCall to signal the VM to loop.
    """
    if n <= 0:
        return "done"
    # Return TailCall for the VM instead of a LazyResult
    return TailCall(kwargs={"n": n - 1})


@cs.task
def heavy_complex_countdown(n: int, _dummy=None):
    """
    A recursive task with a DEEP dependency chain, forcing a significant
    graph build and solve cost on each iteration. This represents the old, slow path.
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
        await asyncio.sleep(0)
    return "done"


async def run_benchmark(
    engine: Engine, target: cs.LazyResult, use_vm: bool = False
) -> float:
    """Runs the target and returns the execution time in seconds."""
    print(f"Running benchmark for '{target.task.name}' (VM: {use_vm})...")
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

    # 1. Run Optimized Path (VM)
    print("[1] Running Optimized VM Path (simple_countdown)...")
    optimized_target = simple_countdown(iterations)
    optimized_time = await run_benchmark(engine, optimized_target, use_vm=True)
    optimized_tps = iterations / optimized_time
    print(f"  Finished in {optimized_time:.4f} seconds.")
    print(f"  TPS: {optimized_tps:,.2f} calls/sec\n")

    # 2. Run Heavy Un-optimized Path (Graph Build)
    print("[2] Running Heavy Un-optimized Path (heavy_complex_countdown)...")
    unoptimized_target = heavy_complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, use_vm=False)
    unoptimized_tps = iterations / unoptimized_time
    print(f"  Finished in {unoptimized_time:.4f} seconds.")
    print(f"  TPS: {unoptimized_tps:,.2f} calls/sec\n")

    # 3. Run Imperative Ground Truth
    print("[3] Running Imperative Ground Truth (imperative_countdown)...")
    imperative_time = await run_imperative_benchmark(iterations)
    imperative_tps = iterations / imperative_time
    print(f"  Finished in {imperative_time:.4f} seconds.")
    print(f"  TPS: {imperative_tps:,.2f} calls/sec\n")

    # 4. Compare Results
    print("--- Comparison ---")
    if unoptimized_tps > 0 and unoptimized_tps != float('inf') and optimized_tps > 0:
        heavy_vs_optimized = optimized_tps / unoptimized_tps
        print(
            f"Optimized (VM) vs. Heavy (Graph): {heavy_vs_optimized:.2f}x faster"
        )

    if imperative_tps > 0 and imperative_tps != float('inf') and optimized_tps > 0:
        overhead_ratio = imperative_tps / optimized_tps
        print(f"Imperative vs. Optimized (VM): Overhead is {overhead_ratio:.2f}x")
        print(
            f"  (The declarative VM path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)"
        )


if __name__ == "__main__":
    asyncio.run(main())
~~~~~

### 下一步建议
现在，请在你的环境中执行这个脚本：
```bash
python observatory/benchmarks/tco_performance.py
```
然后将结果粘贴回来。我们将根据输出结果来评估我们的工作是否成功，并生成最终的 `[COMMIT]` 计划。
