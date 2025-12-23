简要回答
分析非常准确。`heavy_complex_countdown` 性能下降是因为我们在“慢速路径”中引入了**冗余的资源扫描**；而 `simple` 和 `stable` 的上升则归功于 **Hot-Loop Bypass**。

以下是详细分析与修复计划：

1. 性能分析 (Performance Diagnosis)

*   **为什么 `simple` 和 `stable` 变快了？**
    *   它们命中了 `_cycle_cache` 并且满足 `_are_args_simple`（注意：`stable_complex_loop` 在测试脚本中传入的是 `_dummy=static_dep_chain` 的**结果**或预构建的 `LazyResult`，在快速路径中它被视为一个稳定的结构）。
    *   它们进入了 `_execute_hot_node`，直接跳过了 `FlowManager` 的拓扑排序、`NodeProcessor` 的事件发布和 `asyncio.gather` 的调度开销。
*   **为什么 `heavy_complex_countdown` 变慢了 (1.1k -> 440 TPS)？**
    *   **强制慢速路径**: 它的参数中包含 `dep_chain`（一个 10 节点的 `LazyResult` 链）。`_are_args_simple` 检测到 `LazyResult` 会强制走慢速路径。
    *   **冗余扫描 (Redundant Scan)**: 在慢速路径中，我之前的代码在每一轮循环都执行了 `self.resource_container.scan(graph)` 来尝试更新 `_cycle_cache`。对于一个 10 节点的图，这种递归扫描非常昂贵。由于它每一轮都走慢速路径，这个开销被放大了 10000 次。
*   **为什么没能对齐 VM 模式？**
    *   **异步调度成本**: 即使是 `_execute_hot_node`，依然存在 `await executor.execute` 和 `await asyncio.sleep(0)`（TCO 必需的让权）。VM 模式由于是纯同步指令流（直到遇到真正的 I/O），其指令派发开销极低。
    *   **对象创建**: 即使跳过了 `build_graph`，每轮循环依然在创建新的 `LazyResult` 对象和 `instance_map` 字典。

---

## [WIP] perf: 消除慢速路径冗余并增强 TCO 稳定性

### 目标
1.  **按需扫描**: 仅在 `cycle_id` 尚未缓存时才执行资源扫描，避免在慢速路径中重复支付该代价。
2.  **优化 `_are_args_simple`**: 提高判断效率。
3.  **解释性能限制**: 明确“图模式”与“VM 模式”在 Python 异步环境下的物理极限差异。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/tco-fast-path #task/action/fix-regression #task/state/continue

---

### Script

#### Acts 1: 修复慢速路径中的冗余资源扫描
我们必须确保 `scan(graph)` 只在填充缓存的那一刻发生。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    # Cache for Future TCO Fast Path
                    if cycle_id:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (graph, indexed_plan, target_node.id, req_res)

                # 3. Setup Resources (mixed scope)
~~~~~
~~~~~python
                    # Cache for Future TCO Fast Path
                    # Only scan and cache if we haven't already indexed this cycle
                    if cycle_id and cycle_id not in self._cycle_cache:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (graph, indexed_plan, target_node.id, req_res)

                # 3. Setup Resources (mixed scope)
~~~~~

#### Acts 2: 进一步精简 `_execute_hot_node`
减少不必要的参数传递。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
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
~~~~~
~~~~~python
    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        A stripped-down version of NodeProcessor.process specifically for hot TCO loops.
        Bypasses event bus, flow manager, and multiple resolvers for maximum performance.
        """
        # 1. Resolve Arguments (Minimal path)
        # We reuse the node_processor's resolver but bypass the process() wrapper
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
~~~~~

#### Acts 3: 调整 `execute` 循环中的调用
同步修改 `execute` 函数中的调用点。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides
                    )
~~~~~

### 下一步建议
修复了慢速路径中的性能陷阱后，`heavy_complex_countdown` 的性能应该恢复到之前的水平（约 1.1k TPS）。

**关于“对齐 VM 模式”的说明**: 
虽然我们已经极大减少了开销，但“图执行模式”本质上仍然是在每一轮循环中维护一个完整的 `Graph` 对象上下文，并执行一次逻辑上的图遍历（哪怕只有一节点）。VM 模式之所以快，是因为它**没有图**，只有一组扁平的指令。

要真正让图模式达到 VM 的级别，下一步可能需要引入 **Graph-to-Instruction 编译器**：在 `_cycle_cache` 中不存储 Graph，而是存储该 Graph 编译后的 `Blueprint`。如果你有兴趣，我们可以将此作为 3.3 阶段的任务。

现在请再次运行 `tco_performance.py`。
