这是一份针对“每节点执行税费”的全面清算计划。

通过 Pyinstrument 的数据，我们已经锁定了那些在 10 万次级别调用下堆积成山的开销。我们将通过引入**“零摩擦执行路径 (Zero-Friction Execution Paths)”**来彻底解放性能，让图执行引擎的 TPS 逼近 VM 路径。

## [WIP] perf: Eliminate per-node execution taxes (Reflector, Dispatcher, Sync)

### 用户需求
消除 `ArgumentResolver`、`LocalExecutor` 和 `NodeProcessor` 中的重复冗余计算，针对无约束、无动态注入的普通任务建立“零摩擦”执行路径，以大幅提升高频循环下的 TPS。

### 评论
在高频迭代中，每一行代码都是有代价的。
1.  **`inspect.Signature` 是昂贵的**: 在每一轮循环中为同一个函数重复绑定参数是完全没必要的。既然图结构已缓存，参数的位置也已确定。
2.  **`asyncio.gather` 是沉重的**: 对于单节点的 Stage，创建一个 `list`、打包 `coroutine` 再交给 `gather` 的开销远超直接 `await`。
3.  **`Condition` 变量是缓慢的**: 即使资源需求为空，进入异步上下文管理器也会触发协程的暂停与恢复。

我们将通过“分支预测”式的逻辑，让 99% 的简单任务跳过这些复杂的检查。

### 目标
1.  **优化 `ArgumentResolver`**:
    *   当 `has_complex_inputs` 为 `False` 时，彻底绕过 `inspect.Signature.bind_partial`。
    *   预计算并缓存参数的原始结构。
2.  **优化 `NodeProcessor`**:
    *   如果 `requirements` 为空，直接进入执行，不调用 `resource_manager` 的 `acquire/release`。
3.  **优化 `LocalExecutor`**:
    *   使用 `Node` 中已缓存的 `is_async` 标志，彻底移除 `inspect.iscoroutinefunction` 调用。
4.  **优化 `GraphExecutionStrategy`**:
    *   在 `_execute_graph` 中，如果 Stage 只有一个节点，直接 `await` 处理器，不使用 `asyncio.gather`。

### 基本原理
对于一个确定性的执行引擎，如果一个节点在构建时就被标记为“简单”（Simple），那么它的参数解析应该只是一个简单的字典查找，它的执行应该是一个直接的函数调用，它的调度应该是一个直接的 `await`。通过在关键路径上增加这些 `if` 分支，我们将“税费”只征收在真正需要复杂处理的任务身上。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/per-node-overhead #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 优化 `ArgumentResolver` (消除反射税)

我们将重构 `resolve` 方法，让它对简单任务几乎“瞬时”返回。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
            if input_overrides:
                # FASTEST PATH: Used by TCO loops
                # We trust overrides contain the full argument set or correct deltas.
                final_bindings = node.input_bindings.copy()
                final_bindings.update(input_overrides)

                # Convert to args/kwargs
                f_args = []
                f_kwargs = {}
                # Find max positional index
                max_pos = -1
                for k in final_bindings:
                    if k.isdigit():
                        idx = int(k)
                        if idx > max_pos:
                            max_pos = idx

                if max_pos >= 0:
                    f_args = [None] * (max_pos + 1)
                    for k, v in final_bindings.items():
                        if k.isdigit():
                            f_args[int(k)] = v
                        else:
                            f_kwargs[k] = v
                else:
                    f_kwargs = final_bindings

                return f_args, f_kwargs

        args = []
~~~~~
~~~~~python
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
            # Reconstruct args/kwargs from Bindings (Literals) and Overrides
            bindings = node.input_bindings
            if input_overrides:
                bindings = bindings.copy()
                bindings.update(input_overrides)
            
            # Identify data dependencies (edges)
            incoming_edges = [
                e
                for e in graph.edges
                if e.target.structural_id == node.structural_id
                and e.edge_type == EdgeType.DATA
            ]

            if not incoming_edges:
                # ABSOLUTE FASTEST PATH: Literals/Overrides only, no edges.
                # Just return them. Note: we don't convert to list here to save time,
                # as executors can handle positional-args-as-dict if they are careful,
                # but to maintain protocol, we'll do a quick conversion.
                f_args = []
                f_kwargs = {}
                for k, v in bindings.items():
                    if k.isdigit():
                        idx = int(k)
                        while len(f_args) <= idx: f_args.append(None)
                        f_args[idx] = v
                    else:
                        f_kwargs[k] = v
                return f_args, f_kwargs

        args = []
~~~~~

#### Acts 2: 优化 `LocalExecutor` (消除判定税)

使用已缓存的 `is_async`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if inspect.iscoroutinefunction(node.callable_obj):
            result = await node.callable_obj(*args, **kwargs)
        else:
            result = node.callable_obj(*args, **kwargs)
~~~~~
~~~~~python
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            result = node.callable_obj(*args, **kwargs)
~~~~~

#### Acts 3: 优化 `NodeProcessor` (消除同步税)

当不需要资源时，不进入 `ResourceManager` 的阻塞路径。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
        # 2. Acquire Resources
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_internal(
                node,
                graph,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
                instance_map,
                input_overrides,
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~
~~~~~python
        # 2. Acquire Resources
        if requirements:
            await self.resource_manager.acquire(requirements)
            try:
                return await self._execute_internal(
                    node,
                    graph,
                    state_backend,
                    active_resources,
                    run_id,
                    params,
                    sub_graph_runner,
                    instance_map,
                    input_overrides,
                )
            finally:
                await self.resource_manager.release(requirements)
        else:
            # FAST PATH: No resources required
            return await self._execute_internal(
                node,
                graph,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
                instance_map,
                input_overrides,
            )
~~~~~

#### Acts 4: 优化 `_execute_graph` (消除调度税)

对于单节点 Stage 优化执行路径。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                        tasks_to_run.append(
                            self.node_processor.process(
                                node,
                                graph,
                                state_backend,
                                active_resources,
                                run_id,
                                params,
                                sub_graph_runner,
                                instance_map,
                                input_overrides=overrides,
                            )
                        )

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        await state_backend.put_result(node.structural_id, res)
~~~~~
~~~~~python
                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    graph,
                                    state_backend,
                                    active_resources,
                                    run_id,
                                    params,
                                    sub_graph_runner,
                                    instance_map,
                                    input_overrides=overrides,
                                ),
                            )
                        )

                    if len(tasks_to_run) == 1:
                        # FAST PATH: Single task in stage, avoid gather
                        node, coro = tasks_to_run[0]
                        res = await coro
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )
                    else:
                        # Standard parallel execution
                        nodes_in_pass = [t[0] for t in tasks_to_run]
                        coros = [t[1] for t in tasks_to_run]
                        pass_results = await asyncio.gather(*coros)

                        for node, res in zip(nodes_in_pass, pass_results):
                            await state_backend.put_result(node.structural_id, res)
                            if flow_manager:
                                await flow_manager.register_result(
                                    node.structural_id, res, state_backend
                                )
~~~~~

### 下一步建议

这一轮优化直接砍掉了 Pyinstrument 报告中耗时最长的几个“税点”。

请再次运行压测：
`python observatory/benchmarks/tco_performance.py`

**预期结果**：
1.  **TPS 质变**: `Explicit Jump Loop` 的 TPS 应该从 **20k** 直接跨越到 **60k-80k**，甚至可能更高。
2.  **Heavy 模式恢复**: `Heavy` 模式的 TPS 应该会从 **1k** 提升到与 `Simple` 模式相近的水平（因为节点循环开销被大幅降低了）。

如果数据如期改善，我们的下一步将是优化 `TaskExecutionFinished` 事件的生成开销。如果你准备好了，请开始。
