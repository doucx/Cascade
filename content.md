## [WIP] chore(benchmarks): Update TCO benchmark to include VM path

### 摘要头
`# [WIP] chore(benchmarks): Update TCO benchmark to include VM path`

### 用户需求
更新 `tco_performance.py` 脚本，增加对新实现的 VM 执行路径 (`use_vm=True`) 的基准测试。这需要定义一个显式返回 `TailCall` 的任务，并将其性能与现有的 JIT 图构建路径和原生 Python 循环进行对比。

### 评论
这是验证架构升级成果的关键时刻。我们预期 VM 路径的性能应显著优于旧的图构建路径，并接近原生 Python 循环。

### 目标
1.  在脚本中导入 `TailCall`。
2.  定义 `vm_countdown` 任务。
3.  修改 `run_benchmark` 以支持传递 `use_vm` 参数。
4.  在 `main` 中添加 VM 路径的测试步骤。
5.  输出比较结果。

### 基本原理
通过显式的对比，量化 AOT/VM 架构带来的性能收益。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/benchmarks #concept/performance #scope/core #ai/instruct #task/domain/benchmarks #task/object/tco-script #task/action/update #task/state/continue

---

### Script

#### Acts 1: 更新 `tco_performance.py`

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# --- Task Definitions ---
~~~~~
~~~~~python
import asyncio
import time
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.runtime.blueprint import TailCall
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# --- Task Definitions ---
~~~~~

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
    return heavy_complex_countdown(n - 1, _dummy=dep_chain)


async def imperative_countdown(n: int):
~~~~~
~~~~~python
    return heavy_complex_countdown(n - 1, _dummy=dep_chain)


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
~~~~~

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
async def run_benchmark(
    engine: Engine, target: cs.LazyResult, iterations: int
) -> float:
    """Runs the target and returns the execution time in seconds."""
    print(f"Running benchmark for '{target.task.name}'...")
    start_time = time.perf_counter()

    result = await engine.run(target)

    end_time = time.perf_counter()

    assert result == "done"
    return end_time - start_time
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
    # 2. Run Heavy Un-optimized Path
    print("[2] Running Heavy Un-optimized Path (heavy_complex_countdown)...")
    unoptimized_target = heavy_complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, iterations)
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
    if unoptimized_tps > 0:
        heavy_vs_optimized = optimized_tps / unoptimized_tps
        print(
            f"Optimized vs. Heavy (TCO Optimization): {heavy_vs_optimized:.2f}x faster"
        )

    if imperative_tps > 0:
        overhead_ratio = imperative_tps / optimized_tps
        print(f"Imperative vs. Optimized (Framework Overhead): {overhead_ratio:.2f}x")
        print(
            f"  (The optimized declarative path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)"
        )
~~~~~
~~~~~python
    # 2. Run Heavy Un-optimized Path
    print("[2] Running Heavy Un-optimized Path (heavy_complex_countdown)...")
    unoptimized_target = heavy_complex_countdown(iterations)
    unoptimized_time = await run_benchmark(engine, unoptimized_target, iterations)
    unoptimized_tps = iterations / unoptimized_time
    print(f"  Finished in {unoptimized_time:.4f} seconds.")
    print(f"  TPS: {unoptimized_tps:,.2f} calls/sec\n")

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
        print(f"VM vs. Heavy (JIT): {vm_vs_heavy:.2f}x faster")

    if optimized_tps > 0:
        vm_vs_simple = vm_tps / optimized_tps
        print(f"VM vs. Simple (Graph Caching): {vm_vs_simple:.2f}x faster")

    if imperative_tps > 0:
        overhead_ratio = imperative_tps / vm_tps
        print(f"Imperative vs. VM (Framework Overhead): {overhead_ratio:.2f}x")
        print(
            f"  (The VM path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)"
        )
~~~~~

### 下一步建议
运行该脚本！这将是验证我们工作成果的决定性时刻。
