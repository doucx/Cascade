简要回答
非常抱歉，我在生成 `patch_file` 指令时遗漏了必要的 `old_string` 和 `new_string` 区分标记。我将按照协议要求的 3 参数格式（路径、旧字符串块、新字符串块）重新生成完整的执行脚本。

## [WIP] fix: 补全 `patch_file` 参数以实现零开销 TCO 快速通道

### 评论
这次补全将确保零开销 TCO 的逻辑能够正确注入到引擎中。核心在于通过 `input_overrides` 机制实现对缓存图的动态参数注入。

### 用户需求
修正之前失败的指令，补全 `patch_file` 的参数，完成 3.1 阶段的任务。

### 目标
1.  准确修改 `ArgumentResolver` 以支持参数覆盖。
2.  准确修改 `NodeProcessor` 以支持覆盖参数的透传。
3.  在 `GraphExecutionStrategy` 中建立 `_cycle_cache` 并实现快速路径检测。

### 基本原理
快速路径的本质是：如果当前任务与上一次任务属于同一个 TCO 循环（`tco_cycle_id` 相同），且输入参数不含复杂的 `LazyResult`，则无需重新构建图。我们只需要将新参数作为 `overrides` 传给 `ArgumentResolver`，它会优先使用这些值来执行缓存好的 `Node`。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/tco-fast-path #task/action/patch-fix #task/state/continue

---

### Script

#### Acts 1: 修改 `ArgumentResolver` 以支持 `input_overrides`

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        positional_args_dict = {}
        for name, value_raw in node.input_bindings.items():
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(
                value_raw, node.id, state_backend, resource_context, graph
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value
~~~~~
~~~~~python
    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        # Apply overrides if provided (for TCO fast path)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(
                value_raw, node.id, state_backend, resource_context, graph
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value
~~~~~

#### Acts 2: 更新 `NodeProcessor` 接口

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
    async def process(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
        instance_map: Dict[str, Node],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

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
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
        instance_map: Dict[str, Node],
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
        )
~~~~~
~~~~~python
    async def process(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

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

    async def _execute_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )
~~~~~

#### Acts 3: 在 `GraphExecutionStrategy` 中引入 `_cycle_cache`

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()
~~~~~
~~~~~python
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Zero-Overhead TCO Cache
        # Maps tco_cycle_id to (Graph, IndexedPlan, root_node_id)
        # Used to bypass build_graph for structurally stable recursive calls
        self._cycle_cache: Dict[str, Any] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()
~~~~~

#### Acts 4: 实现快速路径逻辑

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, instance_map = build_graph(
                    current_target, registry=self._node_registry
                )

                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )
                target_node = instance_map[current_target._uuid]
                
                # Use template_id for caching. Fallback to id if template_id is missing (should not happen).
                cache_key = target_node.template_id or target_node.id

                # 2. Resolve Plan (With JIT Template Caching)
                if cache_key in self._template_plan_cache:
                    # Hit: Rehydrate the indexed plan using the current graph's nodes.
                    indexed_plan = self._template_plan_cache[cache_key]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    # Miss: Ask solver to resolve.
                    plan = self.solver.resolve(graph)
                    # Index and cache the plan for future reuse.
                    self._template_plan_cache[cache_key] = self._index_plan(graph, plan)

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

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
                )
~~~~~
~~~~~python
    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # Check for Zero-Overhead TCO Fast Path
            cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    graph, indexed_plan, root_node_id = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = next(n for n in graph.nodes if n.id == root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)
                else:
                    # SLOW PATH: Build Graph
                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )
                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[cache_key]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[cache_key] = indexed_plan

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

#### Acts 5: 更新 `_execute_graph` 签名并实现 `_are_args_simple`

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
            else:
                return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
        instance_map: Dict[str, Node],
    ) -> Any:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]
~~~~~
~~~~~python
            else:
                return result

    def _are_args_simple(self, lazy_result: LazyResult) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        for arg in lazy_result.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in lazy_result.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
        instance_map: Dict[str, Node],
        root_input_overrides: Dict[str, Any] = None,
    ) -> Any:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                            instance_map,
                        )
                        for node in executable_this_pass
                    ]
~~~~~
~~~~~python
                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = root_input_overrides if node.id == target_node.id else None
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
                                input_overrides=overrides
                            )
                        )
~~~~~

### 下一步建议
我们已经完成了零开销 TCO 快速通道的逻辑注入。现在请运行 `observatory/benchmarks/tco_performance.py`，你应当能观察到 `simple_countdown` 的 TPS 有了质的飞跃。
