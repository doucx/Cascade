你遇到的测试失败揭示了两个关键点：
1.  **Solver 逻辑漏洞**: `NativeSolver` 在执行拓扑排序时，没有过滤掉 `POTENTIAL` 类型的边。当一个任务存在自递归或循环时，`GraphBuilder` 会创建一条从“真身节点”指向“真身节点”或“影子节点”的 `POTENTIAL` 边。由于真身节点处于 `active_node_ids` 中，Solver 错误地将其计入了入度，导致拓扑排序无法开始（入度不为 0），从而触发了“检测到环路”的错误。
2.  **测试用例过时**: `test_build_graph_no_recursive_shadow_analysis` 是在“非递归分析”时期编写的，它的断言显式禁止了递归分析。由于我们现在的核心任务是**实现**递归分析，这个测试用例需要被更新以符合新的行为预期。

我将生成计划来修复这些问题。

## [WIP] fix(engine): 修正 Solver 过滤逻辑并更新递归分析测试

### 错误分析

**1. `test_deep_recursion_tco` 失败原因**:
在 `countdown` 任务中，`ast_analyzer` 识别出 `countdown -> countdown` 的调用。`GraphBuilder` 随后创建了一条 `POTENTIAL` 边。在 `NativeSolver` 中，它仅根据节点是否是“影子节点”来过滤边，但由于自递归的 `POTENTIAL` 边的起点和终点都是同一个“真身”节点，该边被计入了入度。这导致 `countdown` 节点的入度变为 1，拓扑排序无法将其放入初始执行阶段，最终抛出 `ValueError: Cycle detected`。

**2. `test_build_graph_no_recursive_shadow_analysis` 失败原因**:
该测试预期分析在第一层停止（即不进入 `task_b` 的源码去发现 `task_c`）。但根据新的“递归静态分析”需求，我们现在**需要**发现 `task_c`。因此，该测试的断言与新特性冲突。

### 解决方案
1.  **加固 Solver**: 修改 `NativeSolver`，在构建入度表时明确跳过所有 `EdgeType.POTENTIAL` 类型的边。
2.  **更新测试**: 将 `test_build_graph_no_recursive_shadow_analysis` 重命名为 `test_recursive_shadow_analysis`，并更新其断言以验证递归发现能力（即 `task_c` 应该作为影子节点出现在图中）。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/solver #scope/core #task/domain/testing #task/object/solver-recursion-fix #task/action/patch #task/state/continue

---

### Script

#### Acts 1: 修正 NativeSolver 的边过滤逻辑

我们需要确保 Solver 只关注影响执行顺序的“硬依赖”（如 `DATA`, `SEQUENCE`, `CONDITION`），而忽略用于观测和优化的 `POTENTIAL` 边。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        for edge in graph.edges:
            # An edge is only part of the execution plan if both its source
            # and target are active nodes. This naturally filters out POTENTIAL edges.
            if edge.source.id in active_node_ids and edge.target.id in active_node_ids:
                in_degree[edge.target.id] += 1
                adj_list[edge.source.id].append(edge.target.id)
~~~~~
~~~~~python
        from cascade.graph.model import EdgeType

        for edge in graph.edges:
            # POTENTIAL edges are for observation/TCO and must NOT affect execution scheduling.
            if edge.edge_type == EdgeType.POTENTIAL:
                continue

            # An edge is only part of the execution plan if both its source
            # and target are active nodes.
            if edge.source.id in active_node_ids and edge.target.id in active_node_ids:
                in_degree[edge.target.id] += 1
                adj_list[edge.source.id].append(edge.target.id)
~~~~~

#### Acts 2: 更新 TCO 静态分析测试用例

我们将过时的测试用例更新为“递归发现”模式。

~~~~~act
patch_file
tests/engine/graph/test_build_tco.py
~~~~~
~~~~~python
def test_build_graph_no_recursive_shadow_analysis():
    """
    Ensure that we don't infinitely analyze shadow nodes.
    """

    @task
    def task_c():
        return "C"

    @task
    def task_b():
        return task_c()

    @task
    def task_a():
        return task_b()

    workflow = task_a()
    graph = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
    assert "task_b" in node_names

    # task_c should NOT be in the graph because we stop scanning at task_b
    assert "task_c" not in node_names

    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]
    assert len(potential_edges) == 1
    assert potential_edges[0].source.name == "task_a"
    assert potential_edges[0].target.name == "task_b"
~~~~~
~~~~~python
def test_recursive_shadow_analysis():
    """
    Verify that the builder recursively analyzes potential TCO targets.
    """

    @task
    def task_c():
        return "C"

    @task
    def task_b():
        return task_c()

    @task
    def task_a():
        return task_b()

    workflow = task_a()
    graph = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
    assert "task_b" in node_names
    # task_c should now be present as a shadow node due to recursive analysis
    assert "task_c" in node_names

    # Verify edge chain: a -> b -> c
    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]
    assert len(potential_edges) == 2
    
    # a -> b
    assert any(e.source.name == "task_a" and e.target.name == "task_b" for e in potential_edges)
    # b -> c
    assert any(e.source.name == "task_b" and e.target.name == "task_c" for e in potential_edges)
~~~~~

### 下一步建议
修复 Solver 漏洞后，`test_deep_recursion_tco` 应该能够顺利通过。我们可以进行以下操作：
1.  **提交代码**: 这是一个非常稳定的改进，建议进行一次 `[COMMIT]`。
2.  **性能基准测试**: 运行 `observatory/benchmarks/tco_performance.py`，量化 `A->B->A` 互递归在开启 O(1) 快速通道前后的性能差异。你应该会看到 CPU 占用率显著下降。
3.  **可视化增强**: 现在静态图已经能够“看穿”多层递归，我们可以着手改进 `cs.visualize`，让它在渲染时能用统一的 ID 标识同一个循环中的节点。
