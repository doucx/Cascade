好的，我们立即开始解决这个关键的技术债务。

这确实是一个非常微妙但至关重要的点。我们当前的快速通道过于“乐观”，它错误地将一个为特定数据构建的图缓存，当作了通用的结构模板。这必须被修复，以保证引擎的计算正确性。

我将生成一个计划，在快速通道中引入结构完整性验证，从而彻底解决此问题。

## [WIP] fix(engine): Validate structural integrity in TCO fast path

### 用户需求
根据我们的分析，需要立即修复 TCO 快速通道中的缓存键缺陷。具体来说，是在进入零开销快速通道前，增加一道对图结构完整性的验证，以防止引擎在处理动态变化的递归图时，因使用陈旧缓存而产生错误的计算结果。

### 评论
这是一个至关重要的正确性修复。它承认了仅靠静态分析得出的 `tco_cycle_id` 不足以保证 TCO 循环在运行时的结构稳定性。通过重新引入一个轻量级的参数结构检查 (`_are_args_simple`) 作为进入快速通道的“守卫”，我们可以在不牺牲 `simple` 和 `stable` 路径性能的前提下，强制结构动态变化的 `heavy` 路径回退到安全的、全量图构建的慢速路径。这完美地体现了“正确性优先，后优化”的原则，并从根本上消除了潜在的数据损坏风险。

### 目标
1.  **重构 `GraphExecutionStrategy.execute`**: 在快速通道的入口处，重新引入 `_are_args_simple` 检查。
2.  **实现守卫逻辑**: 如果检查发现当前 TCO 迭代的参数包含 `LazyResult` (即，它是一个“重型”调用)，则**跳过**快速通道，强制执行慢速路径（`build_graph`）。
3.  **保持快速通道**: 如果参数是简单的（不含 `LazyResult`），则允许其继续执行零开销的快速通道逻辑。

### 基本原理
问题的根源在于，`_cycle_cache` 缓存了一个与特定字面量参数绑定的 `Graph` 实例，但我们的快速通道错误地将其用于处理其他具有不同结构参数的调用。这违反了图与数据分离的原则。

解决方案是重新引入 `_are_args_simple` 检查。这个检查是一个成本极低的代理，用于判断递归调用的结构是否稳定。
-   如果返回 `True` (如 `countdown(n-1)`)，说明参数是字面量，图结构极大概率是稳定的，可以安全地使用缓存的图实例进入快速通道。
-   如果返回 `False` (如 `countdown(n-1, _dummy=noop())`)，说明参数是动态的，图结构可能已经改变，**必须**通过 `build_graph` 重新构建图以确保正确性。

通过这种方式，我们建立了一个既能保证正确性又能实现高性能的双路径系统。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/engine #concept/executor #scope/core
#ai/brainstorm
#task/domain/runtime #task/object/tco-fast-path #task/action/unification
#task/state/continue

---

### Script

#### Acts 1: 在快速通道中增加结构验证

我们将修改 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py` 文件。核心改动是在 `execute` 方法的快速通道逻辑块 (`if fast_path_data:`) 内部，加入对 `_are_args_simple(current_target)` 的检查。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
            if fast_path_data:
                # FAST PATH: JIT Cache Hit. Bypass full graph build and orchestration.
                graph, _, root_node_id, required_resources = fast_path_data
                target_node = graph.get_node(root_node_id)

                with ExitStack() as step_stack:
                    self.resource_container.setup(
                        required_resources,
                        active_resources,
                        run_stack,
                        step_stack,
                        run_id,
                    )
                    # Prepare dynamic arguments for this specific iteration
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)

                    # Use the hot-loop executor
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        {current_target._uuid: target_node},  # Minimal instance map
                        input_overrides,
                    )

                if isinstance(result, (LazyResult, MappedLazyResult)):
                    current_target = result
                    await asyncio.sleep(0)  # Yield control in the hot loop
                    continue
                else:
                    return result
~~~~~
~~~~~python
            if fast_path_data:
                # FAST PATH: JIT Cache Hit.
                # We add a guard here: the zero-overhead path is only safe if the
                # arguments are simple literals. If they contain other LazyResults,
                # the graph structure may have changed, and we must fall back to
                # the full build path to ensure correctness.
                if self._are_args_simple(current_target):
                    # Bypass full graph build and orchestration.
                    graph, _, root_node_id, required_resources = fast_path_data
                    target_node = graph.get_node(root_node_id)

                    with ExitStack() as step_stack:
                        self.resource_container.setup(
                            required_resources,
                            active_resources,
                            run_stack,
                            step_stack,
                            run_id,
                        )
                        # Prepare dynamic arguments for this specific iteration
                        input_overrides = {}
                        for i, arg in enumerate(current_target.args):
                            input_overrides[str(i)] = arg
                        input_overrides.update(current_target.kwargs)

                        # Use the hot-loop executor
                        result = await self._execute_hot_node(
                            target_node,
                            graph,
                            state_backend,
                            active_resources,
                            params,
                            {current_target._uuid: target_node},  # Minimal instance map
                            input_overrides,
                        )

                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        await asyncio.sleep(0)  # Yield control in the hot loop
                        continue
                    else:
                        return result
~~~~~

### 下一步建议

我们已经为快速通道增加了结构验证的“安全门”。现在最重要的一步，就是验证这个改动是否达到了我们预期的、正确的行为。

我建议再次运行 `observatory/benchmarks/tco_performance.py` 基准测试。

**预期结果**:
1.  `simple_countdown` 和 `stable_complex_loop` 的性能**应该保持高速**（~70k TPS），因为它们的参数是简单的，可以通过 `_are_args_simple` 检查，继续使用快速通道。
2.  `heavy_complex_countdown` 的性能**应该回落到慢速水平**（~1.1k TPS），因为它无法通过检查，将被强制每次都重建图。
3.  最重要的是，**测试套件现在应该能全部通过**，因为 `test_jit_cache_is_hit_but_graph_is_rebuilt_in_loop` 中 `build_graph` 的调用次数将再次符合 `iterations + 1` 的预期。

这个结果将证明我们成功地构建了一个兼具高性能和正确性的 TCO 引擎。请执行基准测试和完整测试套件，并提供结果。
