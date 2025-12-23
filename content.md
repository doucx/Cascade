好的，我分析了这份全面的测试失败报告。问题清晰地分为三类：

1.  **`TypeError` 和 `AttributeError` in `FlowManager`**:
    *   `TypeError`: `test_flow_manager.py` 中的单元测试在实例化 `FlowManager` 时没有提供新的 `instance_map` 参数。
    *   `AttributeError`: 我在上次重构中删除了 `_get_obj_id` 方法，但 `FlowManager` 的 `__init__` 中仍然在调用它，我需要将其替换为使用 `instance_map` 的新逻辑。

2.  **`KeyError` in `test_state_backends.py`**: 这是一个典型的 ID 不匹配问题。测试代码使用 `LazyResult._uuid`（实例 ID）去查询 mock Redis，但 `StateBackend` 是使用 `Node.id`（结构化哈希 ID）作为键来存储结果的。

3.  **`ValueError: too many values to unpack` in `tests/sdk/tools/`**: `build_graph` 函数的返回值从 2 个增加到了 3 个，但 `visualize` 和 `dry_run` 工具的内部实现以及它们的测试代码没有更新解包逻辑。

我将生成一个计划来一次性解决所有这些问题。

## [WIP] fix(engine): Stabilize runtime post-interning and fix all tests

### 错误分析
测试失败的根源是节点复用（interning）重构后，系统未能统一处理两种不同语义的 ID：`LazyResult._uuid`（实例 ID）和 `Node.id`（结构化哈希 ID）。此问题在多个运行时组件中表现出来：
1.  **`FlowManager`**: 单元测试调用签名过时，并且其内部路由逻辑因调用已被移除的 `_get_obj_id` 方法而崩溃。
2.  **`StateBackend` 交互**: 集成测试在使用 `StateBackend` 时，错误地使用了实例 ID 而非结构化 ID 进行结果查询，导致 `KeyError`。
3.  **SDK 工具**: `cs.visualize` 和 `cs.dry_run` 的实现及其测试用例在调用 `build_graph` 后未能正确解包其新的三元组返回值，导致 `ValueError`。

### 用户需求
修复所有因 `FlowManager` 内部错误、`StateBackend` ID 不匹配以及 `build_graph` 签名变更而导致的 12 个测试失败。

### 评论
这是一个在重大架构重构后典型的、需要全面清理的场景。修复这些问题将使“节点复用”这一核心特性在整个系统中正确集成，并恢复测试套件的稳定性，为后续开发扫清障碍。本次修复将系统性地解决 ID 语义混淆问题，并完成所有必要的 API 调用更新。

### 目标
1.  修复 `FlowManager` 的构造函数调用及其内部逻辑。
2.  修复 `test_state_backends.py`，使其使用正确的 `Node.id` 查询状态。
3.  使用 `sed` 批量修复 `tests/sdk/tools/` 目录下的 `ValueError`。
4.  确保所有 12 个失败的测试全部通过。

### 基本原理
我们将分三步进行修复：
1.  **`FlowManager`**: 在其单元测试中为构造函数提供一个空的 `instance_map` mock。同时，修改其 `__init__` 方法，将对 `_get_obj_id` 的调用替换为通过 `instance_map` 将 `LazyResult._uuid` 转换为 `Node.id` 的正确逻辑。
2.  **`StateBackend`**: 在 `test_state_backends.py` 中，我们将先调用 `build_graph` 来获取 `instance_map`，然后用它来将 `workflow._uuid` 转换为正确的 `Node.id`，再用此 ID 查询 mock Redis。
3.  **SDK 工具**: 我们将遵循用户提示，使用 `sed` 命令对 `tests/sdk/tools/` 目录下的所有 `*.py` 文件执行一次性批量替换，将 `graph, _ = build_graph` 的模式更新为 `graph, _, _ = build_graph`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/graph #comp/tests #concept/interning #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 FlowManager 的 TypeError 和 AttributeError

首先，修复 `FlowManager` 的单元测试和内部实现，这将解决 `TypeError` 和所有 `AttributeError`。

~~~~~act
patch_file
tests/engine/runtime/test_flow_manager.py
~~~~~
~~~~~python
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges

    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C")
    state_backend = InMemoryStateBackend(run_id="test_run")

    # Initial state check
~~~~~
~~~~~python
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    # Create a mock instance_map for the test
    instance_map = {"S": n_map["S"], "A": n_map["A"], "B": n_map["B"]}

    # 4. Initialize Manager & Backend
    manager = FlowManager(graph, target_node_id="C", instance_map=instance_map)
    state_backend = InMemoryStateBackend(run_id="test_run")

    # Initial state check
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            self.downstream_demand[edge.source.id] += 1

            if edge.router:
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key
~~~~~
~~~~~python
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            self.downstream_demand[edge.source.id] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.id][route_node.id] = key
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        return None
~~~~~
~~~~~python
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        elif isinstance(instance, Param):
            # Find the node that represents this param
            for node in self.graph.nodes:
                if node.param_spec and node.param_spec.name == instance.name:
                    return node
        return None
~~~~~

#### Acts 2: 修复 StateBackend 的 KeyError

接下来，修复 `test_state_backends.py` 中因 ID 不匹配导致的 `KeyError`。

~~~~~act
patch_file
tests/sdk/integration/test_state_backends.py
~~~~~
~~~~~python
    # The key of the hash field is the node's UUID
    node_uuid = workflow._uuid
    stored_pickled_data = store[results_key][node_uuid]

    # Verify the stored data is correct
    assert pickle.loads(stored_pickled_data) == 3
~~~~~
~~~~~python
    from cascade.graph.build import build_graph
    
    # The key of the hash field is the node's CANONICAL ID, not its instance UUID
    _, _, instance_map = build_graph(workflow)
    node = instance_map[workflow._uuid]
    
    stored_pickled_data = store[results_key][node.id]

    # Verify the stored data is correct
    assert pickle.loads(stored_pickled_data) == 3
~~~~~

#### Acts 3: 批量修复 SDK 工具中的 ValueError

最后，使用 `sed` 命令批量修复 `tests/sdk/tools/` 目录下的所有 `ValueError`。

~~~~~act
run_command
~~~~~
~~~~~bash
sed -i "s/graph, _ = build_graph/graph, _, _ = build_graph/g" tests/sdk/tools/test_preview.py
sed -i "s/graph, _ = build_graph/graph, _, _ = build_graph/g" tests/sdk/tools/test_visualize.py
sed -i "s/visualize(target: LazyResult\[Any]) -> str:/visualize(target: Any) -> str:/g" packages/cascade-sdk/src/cascade/tools/visualize.py
sed -i "s/_analyze_plan(target: LazyResult\[Any], bus: MessageBus)/_analyze_plan(target: Any, bus: MessageBus)/g" packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~

### 下一步建议
我们已经针对所有已知的 12 个失败案例部署了修复措施。这些修复涵盖了从底层运行时逻辑到上层 SDK 工具的多个层面。

现在，最关键的一步是重新运行完整的测试套件，以验证我们的修复是否彻底、且没有引入新的回归问题。如果所有测试通过，我们就可以自信地关闭这个修复任务，并继续推进路线图的下一阶段。
