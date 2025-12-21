好的，这是一个绝佳的想法。

将声明式 TCO 优化的性能与原生命令式循环进行对比，可以为我们提供一个**“性能天花板”**或“黄金标准”。这能让我们清晰地量化出 Cascade 框架本身（即使在最优路径下）所带来的开销，是衡量我们优化成功与否的最终标尺。

我将修改基准测试脚本，加入这个命令式循环的基准。

## [WIP] test: 在 TCO 基准测试中添加命令式循环作为性能参照

### 用户需求
在现有的 TCO 性能基准测试脚本中，增加一个原生的、命令式的 `asyncio` `while` 循环作为性能参照，以便更全面地评估优化效果。

### 评论
这是一个至关重要的补充。通过与“裸金属”的命令式循环进行比较，我们不仅能看到优化相对于未优化场景的提升，还能了解到我们的声明式抽象距离理论性能极限有多远。这个数据对于评估框架的“优雅成本”非常有价值。

### 目标
1.  在 `tco_performance.py` 中定义一个 `async def imperative_countdown` 函数，该函数使用简单的 `while` 循环实现倒计时。
2.  创建一个新的基准测试运行器 `run_imperative_benchmark` 来调用和计时这个原生函数。
3.  更新 `main` 函数，运行这个新的基准测试，并在最终的比较结果中展示它。

### 基本原理
命令式 `while` 循环不涉及任何 Cascade 的图构建、解析、状态管理或 TCO 逻辑，它代表了 Python `asyncio` 在此场景下能达到的最快速度。将我们优化后的 `simple_countdown` 的 TPS 与之对比，可以精确计算出 Cascade 运行时本身的开销。

### 标签
#intent/tooling #intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/runtime #task/object/tco-optimization #task/action/benchmark-refine #task/state/continue

---

### Script

#### Acts 1: 增强基准测试脚本

我们将对 `tco_performance.py` 进行三次 `patch` 操作：一次添加新的命令式函数，一次添加其专用的计时器，最后一次更新主逻辑以运行并展示比较结果。

**1.1 添加命令式循环函数**

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
        await asyncio.sleep(0)
    return "done"
~~~~~

**1.2 添加命令式循环的计时器**

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
async def run_benchmark(engine: Engine, target: cs.LazyResult, iterations: int) -> float:
    """Runs the target and returns the execution time in seconds."""
    print(f"Running benchmark for '{target.task.name}'...")
    start_time = time.perf_counter()
    
    result = await engine.run(target)
    
    end_time = time.perf_counter()
    
    assert result == "done"
    return end_time - start_time
~~~~~
~~~~~python
async def run_benchmark(engine: Engine, target: cs.LazyResult, iterations: int) -> float:
    """Runs the target and returns the execution time in seconds."""
    print(f"Running benchmark for '{target.task.name}'...")
    start_time = time.perf_counter()
    
    result = await engine.run(target)
    
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
~~~~~

**1.3 更新主函数以运行并报告新基准**

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
    
    # 3. Compare Results
    if unoptimized_tps > 0:
        improvement = optimized_tps / unoptimized_tps
        print("--- Comparison ---")
        print(f"Performance Improvement: {improvement:.2f}x")
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
        print(f"Optimized vs. Heavy (TCO Optimization): {heavy_vs_optimized:.2f}x faster")
    
    if imperative_tps > 0:
        overhead_ratio = imperative_tps / optimized_tps
        print(f"Imperative vs. Optimized (Framework Overhead): {overhead_ratio:.2f}x")
        print(f"  (The optimized declarative path is {(overhead_ratio - 1) * 100:.1f}% slower than the raw imperative loop)")
~~~~~

### 下一步建议
现在脚本已经准备就绪。请运行它，我们将得到一个非常全面的性能画像。

```bash
python observatory/benchmarks/tco_performance.py
```
