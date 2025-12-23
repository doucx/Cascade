这是一个极好的战略决策。

通过引入一个“缓存友好型”的多节点基准测试，我们不仅可以量化 JIT 缓存在理想情况下的性能上限（从而证明其潜力），还可以与“缓存敌对型”的 `heavy_complex_countdown` 形成鲜明对比。这将极大地增强我们对性能优化方向的信心和说服力。

我将执行你的计划：
1.  在 `test_jit_cache_verification.py` 中添加 `test_jit_cache_is_hit_for_complex_stable_structures`，验证多节点图的缓存命中。
2.  在 `tco_performance.py` 中添加 `stable_complex_loop` 基准测试。

## [WIP] test(bench): 引入缓存友好的多节点性能基准测试

### 用户需求
在性能测试和验证测试中引入一个新的基准场景：一个包含多节点依赖但结构完全稳定的 TCO 循环。

### 评论
这个新基准测试是当前架构下 JIT 缓存能力的“最佳代言人”。它将展示：当结构真正稳定时，我们的系统能够达到的性能高度。这将为未来的“模板缓存”优化设定一个清晰的参照目标。

### 目标
1.  **验证**: 在 `test_jit_cache_verification.py` 中添加测试用例，证明复杂但稳定的图结构确实只会触发一次 `solver.resolve`。
2.  **基准**: 更新 `tco_performance.py`，加入 `stable_complex_loop` 测试，并展示其相对于无缓存执行的巨大性能优势。

### 基本原理
通过构造一个在递归调用中不改变任何参数（包括依赖项）的 TCO 循环，我们确保生成的 Merkle Hash 是恒定的。这将强制触发 JIT 缓存命中，从而使得我们在拥有复杂执行计划的同时，又能享受 O(1) 的求解开销。

### 标签
#intent/tooling #intent/test #flow/ready #priority/medium #comp/tests #scope/core #ai/instruct #task/domain/performance #task/object/benchmark #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加缓存命中验证测试 (复杂场景)

我们将添加一个新的测试用例，它使用一个带有内部依赖的、结构稳定的递归任务，来验证缓存命中。

~~~~~act
patch_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~python
    # The 2nd iteration finds the exact same Node.id in _plan_cache and skips resolve().
    assert resolve_spy.call_count == 1
~~~~~
~~~~~python
    # The 2nd iteration finds the exact same Node.id in _plan_cache and skips resolve().
    assert resolve_spy.call_count == 1


@pytest.mark.asyncio
async def test_jit_cache_is_hit_for_complex_stable_structures(mocker):
    """
    Verifies that JIT cache works even for multi-node graphs, 
    as long as the structure is stable.
    """
    
    @cs.task
    def noop():
        return "ok"

    stop_flag = False

    @cs.task
    def complex_stable_recursion(_dep):
        nonlocal stop_flag
        if stop_flag:
            return "done"
        stop_flag = True
        
        # Crucial: We must reuse the EXACT same _dep instance (or a structurally identical one)
        # to ensure the Merkle hash remains stable.
        # Since 'noop()' produces a new LazyResult, but its structure is constant (0 args),
        # passing noop() again will produce the SAME Node.id.
        return complex_stable_recursion(_dep=noop())

    solver = NativeSolver()
    engine = Engine(solver=solver, executor=LocalExecutor(), bus=MessageBus())
    resolve_spy = mocker.spy(solver, "resolve")

    # Initial call with a dependency
    target = complex_stable_recursion(_dep=noop())
    result = await engine.run(target)

    assert result == "done"
    # Even with a dependency graph, resolve should only be called once.
    assert resolve_spy.call_count == 1
~~~~~

#### Acts 2: 更新性能基准测试

在 `tco_performance.py` 中添加新的基准测试项。

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
    # Create a 10-node dependency chain to amplify the build/solve cost
    dep_chain = noop()
    for _ in range(10):
        dep_chain = noop(_dummy=dep_chain)

    return heavy_complex_countdown(n - 1, _dummy=dep_chain)


@cs.task
def vm_countdown(n: int):
~~~~~
~~~~~python
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

    # 3. Run VM Path
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
observatory/benchmarks/tco_performance.py
~~~~~
~~~~~python
    if unoptimized_tps > 0:
        vm_vs_heavy = vm_tps / unoptimized_tps
        print(f"VM vs. Heavy (JIT): {vm_vs_heavy:.2f}x faster")

    if optimized_tps > 0:
~~~~~
~~~~~python
    if unoptimized_tps > 0:
        vm_vs_heavy = vm_tps / unoptimized_tps
        print(f"VM vs. Heavy (Cache Miss): {vm_vs_heavy:.2f}x faster")

    if unoptimized_tps > 0 and stable_tps > 0:
        cache_boost = stable_tps / unoptimized_tps
        print(f"Stable vs. Heavy (Cache Boost): {cache_boost:.2f}x faster")

    if optimized_tps > 0:
~~~~~

### 下一步建议
1.  运行 `pytest tests/engine/runtime/test_jit_cache_verification.py`，确认新的测试用例通过。这将在单元测试层面验证多节点图的缓存机制。
2.  运行 `python observatory/benchmarks/tco_performance.py`。
    *   预期结果：`stable_complex_loop` 的 TPS 应该远高于 `heavy_complex_countdown`。这个差值就是 JIT 缓存在处理复杂图时节省下来的 `solver.resolve` 开销。
    *   如果 `stable_tps` 接近 `simple_countdown` 的 TPS（即使图很复杂），那就证明了 JIT 缓存的巨大威力：它将复杂图的运行成本拉低到了单节点的水平。
