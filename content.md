好的，我分析了测试失败的报告。问题主要有两个根源：

1.  **`ValueError: too many values to unpack`**: 我最近修改了 `build_graph` 函数的返回值，从两个（`graph`, `data_tuple`）增加到了三个（`graph`, `data_tuple`, `instance_map`）。测试套件中所有直接调用此函数的地方都没有更新，导致了解包错误。
2.  **`KeyError` / `DependencyMissingError`**: 在引入节点复用（interning）后，`Node` 的 ID 变成了其结构化哈希，而 `LazyResult` 的 `_uuid` 依然是唯一的实例 ID。在处理路由（`Router`）逻辑时，`ArgumentResolver` 错误地使用了实例 ID (`_uuid`) 去查询 `state_backend`，而后者是使用结构化哈希作为键的，导致无法找到上游任务的结果。

我将生成一个计划来一次性修复这两个问题。

## [WIP] fix(engine): Correct test unpacking and resolver ID usage

### 错误分析
测试套件的失败主要由两个独立的问题引起：
1.  **API 签名变更**: `cascade.graph.build.build_graph` 函数的返回值从 2 个变为 3 个，但测试代码中的解包操作（例如 `graph, _ = build_graph(...)`）未同步更新，导致了大量的 `ValueError`。
2.  **ID 语义混淆**: `ArgumentResolver` 在处理 `Router` 动态路由时，未能正确地将 `LazyResult` 的实例 ID (`_uuid`) 转换为 `Node` 的结构化 ID（哈希），导致在状态后端中查找依赖项结果时失败，从而引发了 `KeyError` 和 `DependencyMissingError`。

### 用户需求
修复所有因 `build_graph` 签名变更和 `ArgumentResolver` ID 使用不当而导致的测试失败。

### 评论
这是一个典型的重构后集成修复。第一个问题是简单的机械性代码更新，而第二个问题则触及了节点复用（interning）架构的核心：必须在整个执行流程中严格区分和正确转换“实例 ID”和“模板 ID”。通过将实例到节点的映射（`instance_map`）传递给解析器，我们能弥合这一差距，确保数据流的正确性。

### 目标
1.  更新所有测试文件中对 `build_graph` 的调用，以适应其新的三元组返回值。
2.  修改 `NodeProcessor` 和 `ArgumentResolver` 的接口，将 `instance_map` 传递下去。
3.  在 `ArgumentResolver` 中使用 `instance_map` 来正确解析 `Router` 依赖项的 `Node.id`。
4.  使测试套件恢复到稳定状态。

### 基本原理
我们将分两步解决问题。首先，通过修改 `NodeProcessor` 和 `ArgumentResolver` 的方法签名，将 `GraphBuilder` 生成的 `instance_map`（从 `_uuid` 到 `Node` 的映射）一路传递到最需要它的地方——`ArgumentResolver._resolve_dependency`。在这里，当解析一个 `Router` 的选定分支时，我们将使用该映射将 `LazyResult._uuid` 转换为正确的 `Node.id`，然后再查询 `state_backend`。其次，我们将对测试代码库进行一次全面的扫描和替换，将所有 `graph, _ = build_graph(...)` 的调用更新为 `graph, _, _ = build_graph(...)`，以解决 `ValueError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/graph #concept/interning #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复参数解析器中的 ID 使用问题

我们将通过修改引擎核心组件的签名，将 `instance_map` 传递给 `ArgumentResolver`，以修复 `DependencyMissingError` 和 `KeyError`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
~~~~~
~~~~~python
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
        instance_map: Dict[str, Node],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_internal(
                node,
                graph,
                data_tuple,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~
~~~~~python
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_internal(
                node,
                graph,
                data_tuple,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
                instance_map,
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node, graph, state_backend, active_resources, data_tuple, user_params=params
        )

        start_time = time.time()
~~~~~
~~~~~python
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
            data_tuple,
            user_params=params,
            instance_map=instance_map,
        )

        start_time = time.time()
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        resource_context: Dict[str, Any],
        data_tuple: Tuple[Any, ...],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        args = []
        kwargs = {}
~~~~~
~~~~~python
        resource_context: Dict[str, Any],
        data_tuple: Tuple[Any, ...],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        args = []
        kwargs = {}
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(edge, node.id, state_backend, graph)
                
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
~~~~~
~~~~~python
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(
                    edge, node.id, state_backend, graph, instance_map
                )
                
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def _resolve_dependency(
        self, edge: Edge, consumer_id: str, state_backend: StateBackend, graph: Graph
    ) -> Any:
        # ** CORE ROUTER LOGIC FIX **
        if edge.router:
            # This edge represents a Router. Its source is the SELECTOR.
            # We must resolve the selector's value first.
            selector_result = self._get_node_result(edge.source.id, consumer_id, "router_selector", state_backend, graph)
            
            # Use the result to pick the correct route.
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )
            
            # Now, resolve the result of the SELECTED route.
            return self._get_node_result(selected_route_lr._uuid, consumer_id, edge.arg_name, state_backend, graph)
        else:
            # Standard dependency
            return self._get_node_result(edge.source.id, consumer_id, edge.arg_name, state_backend, graph)
~~~~~
~~~~~python
    def _resolve_dependency(
        self,
        edge: Edge,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
        instance_map: Dict[str, Node],
    ) -> Any:
        # ** CORE ROUTER LOGIC FIX **
        if edge.router:
            # This edge represents a Router. Its source is the SELECTOR.
            # We must resolve the selector's value first.
            selector_result = self._get_node_result(
                edge.source.id, consumer_id, "router_selector", state_backend, graph
            )

            # Use the result to pick the correct route.
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )

            # Now, resolve the result of the SELECTED route.
            # Convert instance UUID to canonical node ID using the map.
            selected_node = instance_map[selected_route_lr._uuid]
            return self._get_node_result(
                selected_node.id, consumer_id, edge.arg_name, state_backend, graph
            )
        else:
            # Standard dependency
            return self._get_node_result(
                edge.source.id, consumer_id, edge.arg_name, state_backend, graph
            )
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            data_tuple,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                        )
                        for node in executable_this_pass
                    ]
~~~~~
~~~~~python
                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            data_tuple,
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

#### Acts 2: 修复测试中的 `build_graph` 解包错误

现在，我们将修复所有测试文件中因 `build_graph` API 变更导致的 `ValueError`。

~~~~~act
patch_file
tests/engine/adapters/solvers/test_csp.py
~~~~~
~~~~~python
    target = gather(node_a, node_b)

    graph, _ = build_graph(target)

    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)
~~~~~
~~~~~python
    target = gather(node_a, node_b)

    graph, _, _ = build_graph(target)

    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)
~~~~~
~~~~~act
patch_file
tests/engine/adapters/solvers/test_csp.py
~~~~~
~~~~~python
    target = gather(node_a, node_b)

    graph, _ = build_graph(target)

    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
~~~~~
~~~~~python
    target = gather(node_a, node_b)

    graph, _, _ = build_graph(target)

    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
~~~~~
~~~~~act
patch_file
tests/engine/adapters/solvers/test_native.py
~~~~~
~~~~~python
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph, _ = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)
~~~~~
~~~~~python
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph, _, _ = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    r1 = t1()
    r2 = t2(r1)

    graph, _ = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
~~~~~
~~~~~python
    r1 = t1()
    r2 = t2(r1)

    graph, _, _ = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    target = process(param_node)

    graph, _ = build_graph(target)

    assert len(graph.nodes) == 2
~~~~~
~~~~~python
    target = process(param_node)

    graph, _, _ = build_graph(target)

    assert len(graph.nodes) == 2
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    target = echo(env_node)
    graph, _ = build_graph(target)

    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
~~~~~
~~~~~python
    target = echo(env_node)
    graph, _, _ = build_graph(target)

    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build.py
~~~~~
~~~~~python
    # Create a workflow with nested dependencies
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph, _ = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
~~~~~
~~~~~python
    # Create a workflow with nested dependencies
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph, _, _ = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build_tco.py
~~~~~
~~~~~python
    Test that the graph builder detects the potential TCO call from
    orchestrator to leaf_task and creates a POTENTIAL edge.
    """
    workflow = orchestrator(10)
    graph, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "orchestrator" in node_names
~~~~~
~~~~~python
    Test that the graph builder detects the potential TCO call from
    orchestrator to leaf_task and creates a POTENTIAL edge.
    """
    workflow = orchestrator(10)
    graph, _, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "orchestrator" in node_names
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_build_tco.py
~~~~~
~~~~~python
    def task_a():
        return task_b()

    workflow = task_a()
    graph, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
~~~~~
~~~~~python
    def task_a():
        return task_b()

    workflow = task_a()
    graph, _, _ = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_basic_graph():
    """Test serializing a simple linear graph."""
    target = another_task(simple_task(x=10))
    graph, _ = build_graph(target)

    json_str = to_json(graph)
    data = json.loads(json_str)
~~~~~
~~~~~python
def test_serialize_basic_graph():
    """Test serializing a simple linear graph."""
    target = another_task(simple_task(x=10))
    graph, _, _ = build_graph(target)

    json_str = to_json(graph)
    data = json.loads(json_str)
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
    """
    # We use the top-level tasks defined in this module
    target = another_task(simple_task(x=5))
    original_graph, _ = build_graph(target)

    # Serialize
    json_str = to_json(original_graph)
~~~~~
~~~~~python
    """
    # We use the top-level tasks defined in this module
    target = another_task(simple_task(x=5))
    original_graph, _, _ = build_graph(target)

    # Serialize
    json_str = to_json(original_graph)
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_params():
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
~~~~~
~~~~~python
def test_serialize_params():
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_with_retry():
    """Test serialization of retry policy including backoff."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~python
def test_serialize_with_retry():
    """Test serialization of retry policy including backoff."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_with_constraints():
    """Test serialization of resource constraints."""
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~python
def test_serialize_with_constraints():
    """Test serialization of resource constraints."""
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
    # 2. Constraint edge (dynamic)
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))

    graph, _ = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)
~~~~~
~~~~~python
    # 2. Constraint edge (dynamic)
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))

    graph, _, _ = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)
~~~~~
~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
    target = consumer(router)

    # Build and Serialize
    graph, _ = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
~~~~~
~~~~~python
    target = consumer(router)

    # Build and Serialize
    graph, _, _ = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
~~~~~
~~~~~act
patch_file
tests/engine/runtime/test_engine_core.py
~~~~~
~~~~~python
    def task_b(x):
        pass

    workflow = task_b(task_a())
    graph, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~
~~~~~python
    def task_b(x):
        pass

    workflow = task_b(task_a())
    graph, _, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~
~~~~~act
patch_file
tests/spec/spec/test_constraint.py
~~~~~
~~~~~python
    def heavy_task():
        pass

    target = heavy_task().with_constraints(io_bandwidth="high")
    graph, _ = build_graph(target)

    node = next(n for n in graph.nodes if n.name == "heavy_task")

    assert node.constraints is not None
~~~~~
~~~~~python
    def heavy_task():
        pass

    target = heavy_task().with_constraints(io_bandwidth="high")
    graph, _, _ = build_graph(target)

    node = next(n for n in graph.nodes if n.name == "heavy_task")

    assert node.constraints is not None
~~~~~

### 下一步建议
我们已经修复了引擎逻辑中的 ID 解析问题，并修正了测试套件中所有因 API 变更导致的解包错误。现在代码库应该处于一个更稳定的状态。

我建议重新运行完整的测试套件，以确认所有已知的失败都已解决。如果测试通过，我们就可以继续推进路线图的下一个阶段：**2.2 分离的数据提取流程**。
