好的，我分析了新的测试失败报告。问题非常清晰：

1.  **`AttributeError`**: 我的上一次修复在 `FlowManager` 中遗留了一个对已被删除的 `_get_obj_id` 方法的调用。这个 bug 导致了所有与路由（Router）相关的测试（共 5 个）全部失败。
2.  **`ValueError`**: 我修复了 SDK 工具的 *测试*，但忘记修复 SDK 工具本身的 *实现代码*。`visualize()` 和 `dry_run()` 内部仍然在使用旧的 `build_graph` 解包方式，导致了 5 个 `ValueError`。

这是一个典型的“修复不彻底”的问题。我将生成一个计划来一次性解决所有这些遗留问题，使测试套件完全通过。

## [WIP] fix(engine): Finalize interning refactor and fix all tests

### 错误分析
测试失败由两个独立的疏忽引起：
1.  **运行时逻辑错误**: 在 `FlowManager` 的 `should_skip` 方法中，仍然存在对已移除的 `_get_obj_id` 方法的调用，导致所有涉及路由（`Router`）剪枝或解析的逻辑在运行时崩溃。
2.  **SDK 工具未同步**: `cascade.tools.preview` 和 `cascade.tools.visualize` 模块在调用 `build_graph` 后，没有更新其解包逻辑以适应新的三元组返回值，导致 `ValueError`。

### 用户需求
修复 `FlowManager` 中的 `AttributeError` 和 SDK 工具中的 `ValueError`，使所有测试通过。

### 评论
这次修复是“节点复用”重构的收尾工作。通过修正 `FlowManager` 中最后一块逻辑，并使上层工具与底层 API 签名保持一致，我们将彻底解决这次重构引入的所有回归问题。这是恢复代码库稳定性的关键一步。

### 目标
1.  在 `FlowManager.should_skip` 中，将对 `_get_obj_id` 的调用替换为使用 `instance_map` 的正确逻辑。
2.  更新 `cascade.tools.preview._analyze_plan` 的实现以正确解包 `build_graph` 的返回值。
3.  更新 `cascade.tools.visualize.visualize` 的实现以正确解包 `build_graph` 的返回值。
4.  确保所有测试都成功通过。

### 基本原理
我们将直接修改 `flow.py`，用 `self._get_node_from_instance()` 替换掉错误的函数调用，从而修复所有 `AttributeError`。然后，我们将修改 `preview.py` 和 `visualize.py` 中的 `graph, _ = build_graph(target)` 为 `graph, _, _ = build_graph(target)`，从而修复所有 `ValueError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/sdk #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修复 FlowManager 中的 AttributeError

我们将首先定位并修复 `flow.py` 中导致所有路由测试失败的 `AttributeError`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
        active_route_key = None
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            if state_backend.has_result(selector_id):
                active_route_key = state_backend.get_result(selector_id)

        for edge in self.in_edges[node.id]:
~~~~~
~~~~~python
        active_route_key = None
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_node = self._get_node_from_instance(router_edge.router.selector)
            if selector_node:
                selector_id = selector_node.id
                if state_backend.has_result(selector_id):
                    active_route_key = state_backend.get_result(selector_id)

        for edge in self.in_edges[node.id]:
~~~~~

#### Acts 2: 修复 SDK 工具中的 ValueError

现在，我们修复 `visualize` 和 `dry_run` 工具内部因 `build_graph` API 变更导致的 `ValueError`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~
~~~~~python
    # 1. Build the graph statically
    graph, _ = build_graph(target)

    # 2. Resolve the execution plan (topological sort)
~~~~~
~~~~~python
    # 1. Build the graph statically
    graph, _, _ = build_graph(target)

    # 2. Resolve the execution plan (topological sort)
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph, _ = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
~~~~~
~~~~~python
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph, _, _ = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
~~~~~

### 下一步建议
我们已经部署了针对所有剩余失败测试的修复。现在，测试套件应该能够完全通过了。

一旦测试通过，**“第二阶段：构建器演进 - 2.1 节点复用”** 的核心任务就已完成。我们可以继续推进路线图的下一节：**“2.2 分离的数据提取流程”**。
