## [WIP] feat(executor): 将 LocalExecutor 升级为支持异步

### 用户需求
将 `LocalExecutor` 改造为支持同步/异步混合执行，以配合 `Executor` 协议的变更。

### 评论
这是异步支持的关键实现步骤。现在的执行器将能够智能地识别任务类型，如果是 `async def` 定义的任务，它会 `await` 其结果；如果是普通函数，则直接执行。这使得 Cascade 能够无缝混合处理 CPU 密集型任务（同步）和 IO 密集型任务（异步）。

### 目标
1.  修改 `src/cascade/adapters/executors/local.py`：
    -   将 `execute` 方法改为 `async def`。
    -   内部增加逻辑：检查 `node.callable_obj` 是否为协程函数。如果是，使用 `await` 执行；否则保持同步调用。
2.  更新 `tests/test_adapters.py`：
    -   由于 `execute` 变成了异步方法，现有的同步测试会失败。需要使用 `asyncio.run()` 来运行测试中的执行逻辑。

### 基本原理
-   **混合执行模型**: 通过 `inspect.iscoroutinefunction` 在运行时动态分发。
-   **协议一致性**: 实现之前更新的 `Executor` Protocol。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/adapters #concept/async
#task/domain/core #task/object/async-support #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Upgrade LocalExecutor to async

将 `LocalExecutor.execute` 转换为异步方法，并处理同步/异步分发。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
    def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from dependency results and injected resources.
        """
        # 1. Prepare arguments from upstream task results
        kwargs_from_deps: Dict[str, Any] = {}
        positional_args_from_deps = {}

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args_from_deps[int(edge.arg_name)] = result
            else:
                kwargs_from_deps[edge.arg_name] = result

        sorted_indices = sorted(positional_args_from_deps.keys())
        args = [positional_args_from_deps[i] for i in sorted_indices]

        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
            if isinstance(param.default, Inject):
                resource_name = param.default.resource_name
                if resource_name in resource_context:
                    kwargs_from_resources[param.name] = resource_context[resource_name]
                else:
                    raise NameError(
                        f"Task '{node.name}' requires resource '{resource_name}' "
                        "which was not found in the active context."
                    )

        # 3. Combine arguments and execute
        # Dependencies take precedence over resource injections if names conflict
        final_kwargs = {**kwargs_from_resources, **kwargs_from_deps}

        return node.callable_obj(*args, **final_kwargs)
~~~~~
~~~~~python
    async def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from dependency results and injected resources.
        """
        # 1. Prepare arguments from upstream task results
        kwargs_from_deps: Dict[str, Any] = {}
        positional_args_from_deps = {}

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args_from_deps[int(edge.arg_name)] = result
            else:
                kwargs_from_deps[edge.arg_name] = result

        sorted_indices = sorted(positional_args_from_deps.keys())
        args = [positional_args_from_deps[i] for i in sorted_indices]

        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
            if isinstance(param.default, Inject):
                resource_name = param.default.resource_name
                if resource_name in resource_context:
                    kwargs_from_resources[param.name] = resource_context[resource_name]
                else:
                    raise NameError(
                        f"Task '{node.name}' requires resource '{resource_name}' "
                        "which was not found in the active context."
                    )

        # 3. Combine arguments and execute
        # Dependencies take precedence over resource injections if names conflict
        final_kwargs = {**kwargs_from_resources, **kwargs_from_deps}

        if inspect.iscoroutinefunction(node.callable_obj):
            return await node.callable_obj(*args, **final_kwargs)
        else:
            return node.callable_obj(*args, **final_kwargs)
~~~~~

#### Acts 2: Update tests for async executor

更新 `tests/test_adapters.py` 中的 `test_local_executor`，使用 `asyncio.run` 来执行异步的 `execute` 方法。

~~~~~act
patch_file
tests/test_adapters.py
~~~~~
~~~~~python
def test_local_executor():
    def add(x: int, y: int) -> int:
        return x + y

    # Manually construct graph for clarity
    node_x = Node(id="x", name="provide_x", callable_obj=lambda: 5)
    node_y = Node(id="y", name="provide_y", callable_obj=lambda: 10)
    node_add = Node(id="add", name="add", callable_obj=add)

    edge1 = Edge(source=node_x, target=node_add, arg_name="0")  # positional x
    edge2 = Edge(source=node_y, target=node_add, arg_name="y")  # keyword y

    graph = Graph(nodes=[node_x, node_y, node_add], edges=[edge1, edge2])

    # Simulate upstream results
    upstream_results = {"x": 5, "y": 10}

    executor = LocalExecutor()
    result = executor.execute(node_add, graph, upstream_results, resource_context={})

    assert result == 15
~~~~~
~~~~~python
def test_local_executor():
    import asyncio

    def add(x: int, y: int) -> int:
        return x + y

    # Manually construct graph for clarity
    node_x = Node(id="x", name="provide_x", callable_obj=lambda: 5)
    node_y = Node(id="y", name="provide_y", callable_obj=lambda: 10)
    node_add = Node(id="add", name="add", callable_obj=add)

    edge1 = Edge(source=node_x, target=node_add, arg_name="0")  # positional x
    edge2 = Edge(source=node_y, target=node_add, arg_name="y")  # keyword y

    graph = Graph(nodes=[node_x, node_y, node_add], edges=[edge1, edge2])

    # Simulate upstream results
    upstream_results = {"x": 5, "y": 10}

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_add, graph, upstream_results, resource_context={})
    )

    assert result == 15
~~~~~

### 下一步建议
执行 **子任务 3: 引擎异步化**。这是异步改造的最后一步。我们将把 `Engine.run` 改造为异步方法，并确保顶层 `cascade.run` API 能够正确引导事件循环。此外，我们还需要更新 `Engine` 内部调用 `executor.execute` 的方式（添加 `await`）。这一步将使整个系统真正支持异步工作流。
