这是非常棒的进展！`tco_performance.py` 的通过证明了我们修复“真环”和“假环”的策略是极其有效的，性能提升高达 103 倍，这正是我们追求的“通用结构缓存”的效果。

然而，`pytest` 的失败揭示了一个伴生问题：**孤立的影子节点 (Orphaned Shadow Nodes)**。

 错误分析

1.  **现象**: `TypeError: Node ... is not executable (no callable).`
2.  **原因**:
    *   我们之前在 `NativeSolver` 中通过白名单机制过滤掉了 `POTENTIAL` 边。
    *   `GraphBuilder` 为了静态分析创建了 `is_shadow=True` 的节点（影子节点），它们原本通过 `POTENTIAL` 边依附于主图。
    *   当 `POTENTIAL` 边被移除后，这些影子节点失去了所有入边，变成了**孤立节点 (Islands)**。
    *   `NativeSolver` (基于 Kahn 算法) 会将所有入度为 0 的节点放入初始执行队列。
    *   因此，这些仅用于分析、没有 `callable_obj` 的影子节点被错误地调度执行，导致了 `TypeError`。

 修复方案

我们必须在 `NativeSolver` 中显式地过滤掉影子节点。它们是编译期的元数据，绝对不应该出现在运行时的执行计划中。

我将生成一个计划来修补这个漏洞。

## [WIP] fix(engine): Filter out shadow nodes in NativeSolver to prevent execution errors

### 简要回答
基准测试的通过验证了白名单策略的有效性，但测试失败暴露了副作用：忽略连接边后，用于静态分析的影子节点变成了孤立节点并被错误调度。必须在 Solver 中彻底过滤掉它们。

### 摘要头
## [WIP] fix(engine): Filter out shadow nodes in NativeSolver to prevent execution errors

### 用户需求
修复 `tests/engine/runtime/test_engine_recursion.py` 和 `test_tco_mutual_recursion.py` 中的 `TypeError: Node ... is not executable` 错误。

### 评论
这是一个逻辑闭环的修复。我们剥离了元数据边（POTENTIAL），自然也必须剥离元数据节点（Shadow Nodes）。如果不这样做，Solver 就会把它们当作可执行的任务来调度。

### 目标
修改 `NativeSolver.resolve` 方法，在初始化图遍历结构时，从源头上排除所有 `is_shadow=True` 的节点。

### 基本原理
影子节点 (`is_shadow=True`) 的唯一目的是承载静态分析信息（如 TCO 循环结构），它们没有可执行的函数体 (`callable_obj` 为 None)。运行时的 Solver 应当只关注那些真正需要执行的节点（即 `executable_nodes`）。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #concept/solver
#ai/instruct
#task/domain/core #task/object/solver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 NativeSolver 中过滤影子节点

我们将修改 `native.py`。在构建邻接表和入度字典之前，先过滤掉所有 shadow nodes。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        """
        adj: Dict[str, List[Node]] = {node.id: [] for node in graph.nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        node_map: Dict[str, Node] = {node.id: node for node in graph.nodes}

        # Whitelist of edge types that represent actual execution dependencies.
~~~~~
~~~~~python
        """
        # Filter out shadow nodes completely. They are for static analysis only
        # and should never be scheduled for execution.
        executable_nodes = [n for n in graph.nodes if not n.is_shadow]

        adj: Dict[str, List[Node]] = {node.id: [] for node in executable_nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in executable_nodes}
        node_map: Dict[str, Node] = {node.id: node for node in executable_nodes}

        # Whitelist of edge types that represent actual execution dependencies.
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            adj[edge.source.id].append(edge.target)
            in_degree[edge.target.id] += 1

        # Kahn's algorithm for topological sorting
        queue = deque([node.id for node in graph.nodes if in_degree[node.id] == 0])
~~~~~
~~~~~python
        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            # Ensure edge connects executable nodes (ignores edges to/from shadow nodes)
            if edge.source.id not in node_map or edge.target.id not in node_map:
                continue

            adj[edge.source.id].append(edge.target)
            in_degree[edge.target.id] += 1

        # Kahn's algorithm for topological sorting
        queue = deque([node.id for node in executable_nodes if in_degree[node.id] == 0])
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        # If not all nodes were processed, a cycle must exist.
        if processed_count != len(graph.nodes):
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~
~~~~~python
        # If not all nodes were processed, a cycle must exist.
        if processed_count != len(executable_nodes):
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~

### 下一步建议
1.  运行 `pytest tests/engine/runtime/test_engine_recursion.py tests/engine/runtime/test_tco_mutual_recursion.py` 验证修复。
2.  再次运行 `python observatory/benchmarks/tco_performance.py` 确保性能依然达标且没有回归。
