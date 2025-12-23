简要回答
性能提升了约 65%（从 7.7k 到 12.8k），这证明了跳过图构建和求解的有效性。然而，距离 VM 模式的 11w+ TPS 仍有 10 倍左右的差距，这说明**“执行阶段”的编排开销（Orchestration Overhead）**成为了新的瓶颈。

我将生成一个针对性的优化计划（Phase 3.1.2），通过旁路掉冗余的资源扫描、流管理和处理器仪式，使图执行模式真正逼近 VM 的性能。

## [WIP] perf: 实现 TCO 快速通道的执行旁路 (Execution Bypass)

### 错误分析
目前的快速通道虽然跳过了“编译”（Build & Resolve），但“运行”阶段仍然太重：
1.  **重复扫描资源**: `resource_container.scan(graph)` 每轮都在递归扫描整个图，即便图是缓存的。
2.  **流管理器开销**: `FlowManager` 每一轮都在实例化并扫描边，对于结构稳定的循环这是不必要的。
3.  **处理器仪式**: `NodeProcessor` 内部包含大量的 `await`、事件发布和 `asyncio.gather`。即使是单节点任务，这些微小的开销在 10,000 次循环中也会累积成秒级的延迟。
4.  **Telemetry 密度**: 图执行模式每一步都向 `MessageBus` 发送多个事件，而 VM 模式目前是“静默”的。

### 用户需求
进一步压榨 TCO 性能，使 `GraphExecutionStrategy` 在处理稳定循环时达到与 VM 相当的吞吐量。

### 目标
1.  **缓存资源需求**: 在 `_cycle_cache` 中直接存储该循环所需的资源列表。
2.  **实现单节点旁路**: 检测到单节点循环时，直接调用 `executor.execute`，绕过 `FlowManager` 和 `NodeProcessor` 的层层包装。
3.  **减少事件发布**: 在快速通道执行期间，通过一个 `silent` 标志位抑制冗余的事件。

### 基本原理
对于一个稳定的 TCO 循环，我们已经知道它需要什么资源，也知道它不需要复杂的流控制（因为它是单线运行的）。通过在 `GraphExecutionStrategy` 中直接持有 `Node` 对象和预解析的资源需求，我们可以像 VM 一样进行“直通式”调用。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/tco-fast-path #task/action/bypass-optimization #task/state/continue

---

### Script

#### Acts 1: 优化资源扫描逻辑
我们在 `_cycle_cache` 中增加对 `required_resources` 的缓存。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    # Cache for Future TCO Fast Path
                    if cycle_id:
                        self._cycle_cache[cycle_id] = (graph, indexed_plan, target_node.id)

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )
~~~~~
~~~~~python
                    # Cache for Future TCO Fast Path
                    if cycle_id:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (graph, indexed_plan, target_node.id, req_res)

                # 3. Setup Resources (mixed scope)
                if fast_path_data:
                    required_resources = fast_path_data[3]
                else:
                    required_resources = self.resource_container.scan(graph)

                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )
~~~~~

#### Acts 2: 实现“热循环”旁路 (Hot-Loop Bypass)
如果检测到该循环只有单阶段且单节点，我们将跳过 `_execute_graph`，直接进行最小化执行。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                # 4. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    input_overrides,
                )
~~~~~
~~~~~python
                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        run_id,
                        params,
                        instance_map,
                        input_overrides
                    )
                else:
                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        input_overrides,
                    )
~~~~~

#### Acts 3: 在 `GraphExecutionStrategy` 中实现 `_execute_hot_node`
这个方法是 `NodeProcessor.process` 的极简版，去掉了事件发布和不必要的解析。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
~~~~~
~~~~~python
    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        A stripped-down version of NodeProcessor.process specifically for hot TCO loops.
        Bypasses event bus, flow manager, and multiple resolvers for maximum performance.
        """
        # 1. Resolve Arguments (Minimal path)
        args, kwargs = self.node_processor.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )

        # 2. Direct Execution (Skip NodeProcessor ceremony)
        result = await self.node_processor.executor.execute(node, args, kwargs)
        
        # 3. Minimal State Update
        state_backend.put_result(node.id, result)
        return result

    async def _execute_graph(
        self,
        target: Any,
~~~~~

### 下一步建议
通过 Acts 3 中的 `_execute_hot_node`，我们绕过了整个 `FlowManager` 的循环检测和 `NodeProcessor` 的事件发送，这两个操作通常是异步代码中非常昂贵的。

请再次运行 `observatory/benchmarks/tco_performance.py`。如果你发现 `simple_countdown` 的 TPS 现在达到了 **50,000 - 80,000**（虽然受限于 Python 的 `await` 开销可能仍低于 VM 的 11w，但应该已经处于同一个量级），那么我们的优化就是成功的。

如果性能仍未达到预期，我们可能需要考虑在 `_execute_hot_node` 中进一步消除 `ArgumentResolver.resolve` 的开销。
