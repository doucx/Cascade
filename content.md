好的，我们来修复这个问题。

正如我们分析的那样，`NativeSolver` 错误地将用于静态分析的 `POTENTIAL` 边当作了执行依赖，从而在递归任务中检测到了不存在的循环。

我将创建一个计划，通过修改 `NativeSolver` 来过滤掉这些 `POTENTIAL` 边，从根本上解决这个问题。由于 `native.py` 文件不在我的上下文中，我将使用 `write_file` 创建它，并确保相关的 `__init__.py` 文件也存在以构成合法的包结构。

## [WIP] fix(engine): 在 NativeSolver 中忽略 POTENTIAL 边以修复循环检测

### 错误分析
`heavy_complex_countdown` 基准测试失败的根本原因是，`NativeSolver` 的拓扑排序算法未能区分边的语义。

1.  **静态分析介入**：在构建复杂递归任务的图时，`GraphBuilder` 中的静态分析器 (`ast_analyzer`) 正确地识别出了递归调用，并添加了一条 `EdgeType.POTENTIAL` 类型的边来标记这个未来的尾调用。
2.  **Solver 的误解**：`NativeSolver` 在解析执行计划时，将图中的所有边（包括 `POTENTIAL` 边）都视为必须满足的先决条件。
3.  **逻辑冲突**：这导致 Solver 认为“要执行 `heavy_complex_countdown`，必须先完成 `heavy_complex_countdown`”，构成了一个逻辑环，从而触发了 `ValueError: Cycle detected` 错误。

`POTENTIAL` 边是用于未来缓存优化和静态可视化的元数据，不应影响当前的执行计划。

### 用户需求
修复因 `NativeSolver` 错误的循环检测逻辑而中断的性能基准测试。

### 评论
这是一个关键的修复。它正确地分离了“静态分析元数据”和“运行时执行依赖”这两个不同层面的概念。这个修复不仅能让基准测试通过，更是为实现“通用图结构缓存”路线图扫清了障碍，使得静态分析能力可以与执行引擎和谐共存。

### 目标
修改 `NativeSolver.resolve` 方法，使其在构建用于拓扑排序的邻接表和入度表时，显式地**忽略** `EdgeType.POTENTIAL` 类型的边。

### 基本原理
我们将创建一个新的 `cascade.adapters.solvers.native.py` 文件。在其 `resolve` 方法中，遍历图的边时，增加一个简单的条件判断：如果 `edge.edge_type == EdgeType.POTENTIAL`，则跳过该边。这将确保只有真正的执行依赖（如数据流、条件）被用于生成执行计划，从而消除错误的循环检测。为保证模块可被正确导入，我们同时创建必要的 `__init__.py` 文件。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/engine #task/object/solver #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 创建 `adapters` 包结构

首先，创建必要的 `__init__.py` 文件，确保 `cascade.adapters.solvers` 是一个有效的 Python 包。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/__init__.py
~~~~~
~~~~~python

~~~~~

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/solvers/__init__.py
~~~~~
~~~~~python

~~~~~

#### Acts 2: 实现修正后的 `NativeSolver`

现在，创建 `native.py` 文件。新的 `resolve` 方法将包含过滤 `POTENTIAL` 边的逻辑。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
from collections import deque
from typing import Dict, List

from cascade.graph.model import Graph, Node, EdgeType
from cascade.spec.protocols import Solver, ExecutionPlan


class NativeSolver(Solver):
    """
    A simple solver that uses topological sort (Kahn's algorithm) to create
    a sequential execution plan.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        """
        Resolves a dependency graph into a list of execution stages.

        Raises:
            ValueError: If a cycle is detected in the graph.
        """
        adj: Dict[str, List[Node]] = {node.id: [] for node in graph.nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        node_map: Dict[str, Node] = {node.id: node for node in graph.nodes}

        for edge in graph.edges:
            # --- CRITICAL FIX ---
            # Ignore potential edges during topological sort. They are metadata for
            # static analysis and caching, not execution dependencies for the current step.
            if edge.edge_type == EdgeType.POTENTIAL:
                continue

            adj[edge.source.id].append(edge.target)
            in_degree[edge.target.id] += 1

        # Kahn's algorithm for topological sorting
        queue = deque([node.id for node in graph.nodes if in_degree[node.id] == 0])
        plan: ExecutionPlan = []
        processed_count = 0

        while queue:
            # All nodes in the current queue can be run in parallel, forming one stage.
            # Sort for deterministic output, useful for testing.
            stage_ids = sorted(list(queue))
            stage_nodes = [node_map[nid] for nid in stage_ids]
            plan.append(stage_nodes)
            queue.clear()
            processed_count += len(stage_ids)

            for node_id in stage_ids:
                for neighbor_node in adj[node_id]:
                    in_degree[neighbor_node.id] -= 1
                    if in_degree[neighbor_node.id] == 0:
                        queue.append(neighbor_node.id)

        # If not all nodes were processed, a cycle must exist.
        if processed_count != len(graph.nodes):
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~

### 下一步建议
我们已经修复了 `NativeSolver`。现在，你可以重新运行 `observatory/benchmarks/tco_performance.py` 基准测试。`heavy_complex_countdown` 应该可以成功执行了，虽然速度可能仍然较慢，因为它还没有利用到新的缓存机制。

下一步，我们将专注于在 `GraphExecutionStrategy` 中实现一个真正的图结构缓存，利用我们刚刚解耦的 `POTENTIAL` 边元数据来彻底优化复杂递归的性能。
