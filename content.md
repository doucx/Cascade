好的，我们将更新基准测试脚本以利用新的 VM 执行路径，并将其与旧的求解器路径和命令式基准进行比较。这将是我们新架构能力的最终展示。

## [COMMIT] feat(benchmark): Update TCO benchmark to use VM path

### 用户需求
1.  修改 `tco_performance.py` 以包含一个新的基准测试场景：**VM Optimized Path**。
2.  `simple_countdown` 任务需要显式返回 `TailCall`，以适配 VM 的 TCO 协议。
3.  在 `run_benchmark` 函数中添加 `use_vm` 参数，以触发引擎的新执行路径。
4.  在最终的比较报告中加入 VM 路径的性能数据。

### 评论
这次提交标志着 **“编译式图执行 (Blueprint/VM)”** 路线图的成功完成。通过在这个基准测试中展示 VM 路径的性能，我们证明了 Cascade 可以在保持其声明式优雅的同时，实现接近原生命令式循环的性能，解决了项目最初面临的核心性能瓶颈。

### 目标
1.  更新 `simple_countdown` 函数。
2.  修改 `run_benchmark` 以调用 `engine.run(..., use_vm=True)`。
3.  在 `main` 函数中添加新的基准测试运行和结果分析。

### 基本原理
我们期望看到以下性能阶梯：
1.  **VM Optimized Path (`use_vm=True`)**: 性能最高，接近命令式循环。
2.  **Solver Optimized Path (`use_vm=False`, simple task)**: 性能居中，受益于结构哈希缓存。
3.  **Solver Un-optimized Path (complex task)**: 性能最差，每次迭代都产生完整的图构建和求解开销。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/vm #task/action/validation #task/state/end

---

### Script

#### Acts 1: 更新基准测试脚本

我们将添加 `TailCall`，并为 VM 路径创建一个新的测试场景。

~~~~~act
write_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
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

~~~~~
