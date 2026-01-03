Excellent catch. You've correctly identified a regression caused by our last refactoring. I removed `node.callable_obj` but failed to update `ResourceContainer.scan`, which still relied on it to inspect function signatures for `Inject` markers.

This is a perfect example of why a strong test suite is critical during refactoring. Let's fix this immediately. The `ExecutableRegistry` we just created is the new source of truth for callables, and we must now pass it to the `scan` method.

I will generate a plan to correct this oversight.

## [WIP] fix(engine): Update ResourceContainer to use ExecutableRegistry

### 错误分析
在 `refactor(core): 解耦 Node 对象与 Python callables` 的提交中，我成功地从 `Node` 对象中移除了 `callable_obj` 属性，以实现图的纯粹性。然而，我遗漏了一个关键的依赖点：`ResourceContainer.scan` 方法仍然试图访问 `node.callable_obj` 来扫描任务签名的默认参数，以发现 `Inject` 标记。这导致了您报告的 `AttributeError`。

### 用户需求
修复因 `callable_obj` 属性被移除而导致的 `AttributeError`，使 `ResourceContainer` 能够正确地扫描资源依赖。

### 评论
这是一个典型的重构后遗症，它凸显了将“数据” (`Graph`) 与“运行时上下文” (`ExecutableRegistry`) 分离的重要性。解决方案很明确：需要运行时信息的组件（如 `ResourceContainer`）必须从运行时上下文（`ExecutableRegistry`）而不是从静态数据（`Graph`）中获取这些信息。

### 目标
1.  修改 `ResourceContainer.scan` 的方法签名，使其接收 `executable_registry` 作为参数。
2.  更新 `ResourceContainer.scan` 的内部实现，从传入的 `executable_registry` 中查找节点对应的 callable，而不是尝试访问 `node.callable_obj`。
3.  更新 `GraphExecutionStrategy` 中的调用点，将 `executable_registry` 传递给 `scan` 方法。

### 基本原理
此修复遵循了我们在上一步中建立的新架构原则：`Graph` 是纯粹的数据，而 `ExecutableRegistry` 是其在特定运行中的可执行实现。任何需要访问函数对象的代码都必须通过 `ExecutableRegistry` 进行。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 ResourceContainer 以使用 ExecutableRegistry

我们将修改 `ResourceContainer.scan`，使其接收 `executable_registry`，并用它来查找节点的 callable 以进行签名扫描。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python.old
    def scan(self, graph: Graph) -> Set[str]:
        required = set()

        # 1. Scan Node Input Bindings for explicit Inject objects
        for node in graph.nodes:
            for value in node.input_bindings.values():
                self._scan_item(value, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            if node.callable_obj:
                try:
                    # Inspect the callable object directly since Node no longer caches the signature
                    obj_to_inspect: Any = node.callable_obj
                    sig = inspect.signature(obj_to_inspect)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required
~~~~~
~~~~~python.new
    def scan(self, graph: Graph, executable_registry: Dict[str, Callable]) -> Set[str]:
        required = set()

        # 1. Scan Node Input Bindings for explicit Inject objects
        for node in graph.nodes:
            for value in node.input_bindings.values():
                self._scan_item(value, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            callable_obj = executable_registry.get(node.current_node_instance_hash)
            if callable_obj:
                try:
                    # Inspect the callable object directly
                    obj_to_inspect: Any = callable_obj
                    sig = inspect.signature(obj_to_inspect)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required
~~~~~

#### Acts 2: 更新 GraphExecutionStrategy 中的调用点

现在，我们在 `GraphExecutionStrategy` 中调用 `scan` 方法时，将 `executable_registry` 传递进去。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                        executable_registry,
                    )

                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
~~~~~
~~~~~python.new
                        executable_registry,
                    )

                required_resources = self.resource_container.scan(
                    graph, executable_registry
                )
                self.resource_container.setup(
                    required_resources,
                    active_resources,
~~~~~

### 下一步建议
问题已修复。我们现在可以安全地回到原定的重构计划，开始实施**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。我将准备执行此步骤的计划。
