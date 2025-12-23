是的，完全正确。

`build_graph` 的返回值签名已经从 `Graph` 变成了 `(Graph, DataTuple)`，但这个测试用例显式调用了 `build_graph` 来准备 Mock 数据，却没有适配新的返回值，因此拿到了一个元组而不是图对象。

我们需要更新这个测试文件来解包返回值。

## [WIP] fix(tests): 适配 test_engine_core 到新 build_graph 签名

### 用户需求
修复 `tests/engine/runtime/test_engine_core.py` 中的 `AttributeError`，使其正确解包 `build_graph` 的返回值。

### 评论
由于 `Engine` 内部已经适配了新的 `build_graph`，所以那些只调用 `Engine.run()` 的集成测试（如 `test_resource_scheduling.py`）已经可以通过了。现在我们需要修复那些手动调用构建器进行 Setup 的单元测试。

### 目标
修改 `test_engine_core.py`，将 `graph = build_graph(...)` 更改为 `graph, _ = build_graph(...)`。

### 基本原理
忽略返回的数据元组，因为在这个特定的测试中，我们在手动构造 Mock Plan，只关心图的拓扑结构（Nodes）来获取节点引用，并不关心运行时数据。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/engine #ai/instruct #task/domain/testing #task/object/unit-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复测试用例

~~~~~act
patch_file
tests/engine/runtime/test_engine_core.py
~~~~~
~~~~~python
    workflow = task_b(task_a())
    graph = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~
~~~~~python
    workflow = task_b(task_a())
    graph, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~

### 下一步建议
现在核心引擎逻辑 (`Engine`) 和核心测试 (`test_engine_core`) 都已适配完毕。

接下来的工作量主要在于清理剩下的测试套件。大量的 `AttributeError: 'tuple' object has no attribute 'nodes'` 表明还有很多测试文件（特别是 `tests/engine/graph/test_build.py` 和可视化工具测试）需要类似的解包修复。

建议执行一个批量修复计划：**[WIP] chore(tests): 批量适配测试套件到新 GraphBuilder 签名**。
