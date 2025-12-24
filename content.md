## [WIP] fix(engine): 修复 Solver 中过时的 is_shadow 引用

### 错误分析
在上一轮 `Node` 模型清理中，我移除了 `is_shadow` 属性（因为它是用于隐式 TCO 分析的）。然而，`NativeSolver` 和 `CSPSolver` 的实现中仍然残留着对 `node.is_shadow` 的引用，用于过滤非执行节点。由于 `Node` 对象不再拥有此属性，导致所有依赖 Solver 的测试（即绝大多数测试）都抛出了 `AttributeError`。

### 用户需求
修复 `NativeSolver` 和 `CSPSolver`，移除对已不存在的 `is_shadow` 属性的引用。

### 评论
这是一个典型的清理不彻底导致的回归。`is_shadow` 是旧时代的遗物，用于区分“实际要跑的节点”和“静态分析推断出的可能节点”。既然我们废弃了隐式静态分析，图中就不应该再有“影子节点”了。所有的节点都是真实的。

### 目标
1.  修改 `cascade-engine/src/cascade/adapters/solvers/native.py`，移除 `is_shadow` 过滤逻辑。
2.  修改 `cascade-engine/src/cascade/adapters/solvers/csp.py`，移除 `is_shadow` 过滤逻辑。

### 基本原理
直接删除相关过滤代码即可。现在的 `GraphBuilder` 只会构建真实的、明确的执行图，不会生成 shadow nodes。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/core #ai/instruct #task/domain/engine #task/object/solver #task/action/cleanup #task/state/end

---

### Script

#### Acts 1: 修复 NativeSolver

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        """
        Resolves a dependency graph into a list of execution stages.

        Raises:
            ValueError: If a cycle is detected in the graph.
        """
        # Filter out shadow nodes completely. They are for static analysis only
        # and should never be scheduled for execution.
        executable_nodes = [n for n in graph.nodes if not n.is_shadow]

        adj: Dict[str, List[Node]] = {
            node.structural_id: [] for node in executable_nodes
        }
        in_degree: Dict[str, int] = {node.structural_id: 0 for node in executable_nodes}
        node_map: Dict[str, Node] = {
            node.structural_id: node for node in executable_nodes
        }
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        """
        Resolves a dependency graph into a list of execution stages.

        Raises:
            ValueError: If a cycle is detected in the graph.
        """
        executable_nodes = graph.nodes

        adj: Dict[str, List[Node]] = {
            node.structural_id: [] for node in executable_nodes
        }
        in_degree: Dict[str, int] = {node.structural_id: 0 for node in executable_nodes}
        node_map: Dict[str, Node] = {
            node.structural_id: node for node in executable_nodes
        }
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            # Ensure edge connects executable nodes (ignores edges to/from shadow nodes)
            if (
                edge.source.structural_id not in node_map
                or edge.target.structural_id not in node_map
            ):
                continue

            adj[edge.source.structural_id].append(edge.target)
~~~~~
~~~~~python
        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            # Ensure edge connects executable nodes
            if (
                edge.source.structural_id not in node_map
                or edge.target.structural_id not in node_map
            ):
                continue

            adj[edge.source.structural_id].append(edge.target)
~~~~~

#### Acts 2: 修复 CSPSolver

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        from cascade.graph.model import EdgeType

        # 0. Filter out Shadow Nodes
        shadow_ids = {
            edge.target.structural_id
            for edge in graph.edges
            if edge.edge_type == EdgeType.POTENTIAL
        }
        active_nodes = [
            node for node in graph.nodes if node.structural_id not in shadow_ids
        ]

        if not active_nodes:
            return []

        # 1. Preprocessing: Extract static resource requirements
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 0. Active Nodes
        active_nodes = graph.nodes

        if not active_nodes:
            return []

        # 1. Preprocessing: Extract static resource requirements
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
        # We try max_stages from 1 to n_nodes.
        # In the worst case (full serial), we need n_nodes stages.
        for max_stages in range(1, n_nodes + 1):
            solution = self._solve_csp(
                graph, active_nodes, shadow_ids, node_resources, max_stages
            )
            if solution:
                break
~~~~~
~~~~~python
        # We try max_stages from 1 to n_nodes.
        # In the worst case (full serial), we need n_nodes stages.
        for max_stages in range(1, n_nodes + 1):
            solution = self._solve_csp(
                graph, active_nodes, node_resources, max_stages
            )
            if solution:
                break
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
    def _solve_csp(
        self,
        graph: Graph,
        active_nodes: list,
        shadow_ids: set,
        node_resources: Dict[str, Dict[str, float]],
        max_stages: int,
    ) -> Optional[Dict[str, int]]:
        from cascade.graph.model import EdgeType

        problem = constraint.Problem()
~~~~~
~~~~~python
    def _solve_csp(
        self,
        graph: Graph,
        active_nodes: list,
        node_resources: Dict[str, Dict[str, float]],
        max_stages: int,
    ) -> Optional[Dict[str, int]]:
        from cascade.graph.model import EdgeType

        problem = constraint.Problem()
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
        # Constraint 1: Dependencies
        # If A -> B, then stage(A) < stage(B)
        for edge in graph.edges:
            # Skip POTENTIAL edges and edges involving shadow nodes
            if edge.edge_type == EdgeType.POTENTIAL:
                continue
            if (
                edge.source.structural_id in shadow_ids
                or edge.target.structural_id in shadow_ids
            ):
                continue

            # Note: We use a lambda that captures nothing, args are passed by value in addConstraint
            problem.addConstraint(
                lambda s_src, s_tgt: s_src < s_tgt,
                (edge.source.structural_id, edge.target.structural_id),
            )
~~~~~
~~~~~python
        # Constraint 1: Dependencies
        # If A -> B, then stage(A) < stage(B)
        for edge in graph.edges:
            # Skip POTENTIAL edges
            if edge.edge_type == EdgeType.POTENTIAL:
                continue

            # Note: We use a lambda that captures nothing, args are passed by value in addConstraint
            problem.addConstraint(
                lambda s_src, s_tgt: s_src < s_tgt,
                (edge.source.structural_id, edge.target.structural_id),
            )
~~~~~

### 下一步建议
这次修复应该能解决所有的 `AttributeError`。请再次运行测试。

我们期望所有与图执行相关的测试（包括 `test_explicit_control_flow.py`, `test_static_integrity.py` 以及现有的 `test_router_pruning.py`, `test_build.py` 等）都能通过。这将标志着我们不仅引入了新的控制流机制，而且成功地清除了旧机制，保持了系统的整体健康。
