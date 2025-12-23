简要回答：
好的，我将执行“第一阶段”的紧急修复方案，通过修改 Solver 逻辑来剔除影子节点，并修正目标节点的定位策略。这将解决 TCO 失效和参数注入错误。

## [WIP] fix(engine): 隔离静态分析元数据并修正目标节点定位

### 错误分析
1.  **参数缺失 (TypeError)**: `GraphExecutionStrategy` 错误地假设 `graph.nodes[-1]` 是目标节点。引入 AST 分析后，`graph.nodes` 末尾追加了“影子节点”（Shadow Nodes），导致初始参数被错误地注入给了影子节点，而真正的根节点（Root Node）因缺少参数而在执行时崩溃。
2.  **TCO 失效 (Resource Leak)**: `NativeSolver` 将“影子节点”纳入了执行计划。由于影子节点通过 `POTENTIAL` 边与主任务连接，这破坏了 TCO 仅在“尾调用”时发生的假设，导致资源无法及时释放，递归深度增加。

### 用户需求
1.  **Solver 隔离**: 修改求解器，使其在生成 `ExecutionPlan` 时完全忽略 `POTENTIAL` 边及其指向的影子节点。
2.  **精确定位**: 修改执行策略，废弃基于索引（`[-1]`）的目标节点查找方式，采用更稳健的定位逻辑（基于 `GraphBuilder` 的 Top-Down 特性，`nodes[0]` 必定是 Root）。

### 评论
这是一次关键的架构“保卫战”。通过在执行层面彻底过滤掉静态分析产生的元数据，我们确立了“观测不影响执行”的原则。这不仅修复了当前的回归错误，也为未来引入更复杂的静态分析工具（如死锁检测、资源预估）铺平了道路，因为我们确信这些分析不会干扰运行时的稳定性。

### 目标
1.  修改 `NativeSolver` 和 `CSPSolver`，使其在拓扑排序前过滤掉所有影子节点（即 `POTENTIAL` 边的目标）。
2.  修改 `GraphExecutionStrategy._update_graph_literals`，将目标节点定位逻辑从 `nodes[-1]` 修正为 `nodes[0]`。
3.  通过 `test_deep_recursion_tco` 和 `test_resource_release_in_recursion` 测试。

### 基本原理
1.  **过滤影子节点**: 影子节点仅由 `POTENTIAL` 边引入。在 Solver 层面，任何作为 `POTENTIAL` 边目标的节点都应被视为“不存在于动态执行图中”。剔除它们可以保证生成的 Plan 纯净。
2.  **修正 Root 定位**: `GraphBuilder` 采用先序遍历（Top-Down）构建图，这意味着 `target` 对应的节点总是第一个被加入 `graph.nodes` 列表的。因此，`nodes[0]` 是指向 Root 的稳定指针，而 `nodes[-1]` 是脆弱的，容易受到子节点或影子节点追加的影响。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/solver #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修改 Solver 以忽略影子节点

我们将修改 `NativeSolver` 和 `CSPSolver`。核心逻辑是：识别所有由 `POTENTIAL` 边指向的节点（影子节点），并将它们从待调度的节点集合中彻底剔除。同时，在构建依赖关系时忽略 `POTENTIAL` 边。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
from typing import Dict, List, Set
from cascade.graph.model import Graph
from cascade.spec.protocols import ExecutionPlan


class NativeSolver:
    """
    A solver that produces a staged execution plan (layered topological sort).
    Nodes in the same stage have no dependencies on each other and can be run in parallel.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 1. Calculate in-degrees for all nodes
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        adj_list: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}

        for edge in graph.edges:
            in_degree[edge.target.id] += 1
            adj_list[edge.source.id].append(edge.target.id)

        # 2. Identify initial layer (nodes with 0 in-degree)
        current_stage = [node for node in graph.nodes if in_degree[node.id] == 0]

        # Sort stage by name for deterministic behavior
        current_stage.sort(key=lambda n: n.name)

        plan: ExecutionPlan = []
        processed_count = 0

        while current_stage:
            plan.append(current_stage)
            processed_count += len(current_stage)
            next_stage_nodes: Set[str] = set()

            # 3. Simulate execution of current stage
            for node in current_stage:
                # For each downstream neighbor
                for neighbor_id in adj_list[node.id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        next_stage_nodes.add(neighbor_id)

            # Prepare next stage
            # We need to map IDs back to Node objects.
            # Optimization: could use a lookup dict, but graph.nodes is usually small enough.
            # Let's create a lookup for speed.
            node_lookup = {n.id: n for n in graph.nodes}

            next_stage = [node_lookup[nid] for nid in next_stage_nodes]
            next_stage.sort(key=lambda n: n.name)  # Deterministic

            current_stage = next_stage

        # 4. Cycle detection
        if processed_count < len(graph.nodes):
            # Finding the cycle is complex, for now raise a generic error
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~
~~~~~python
from typing import Dict, List, Set
from cascade.graph.model import Graph, EdgeType
from cascade.spec.protocols import ExecutionPlan


class NativeSolver:
    """
    A solver that produces a staged execution plan (layered topological sort).
    Nodes in the same stage have no dependencies on each other and can be run in parallel.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 0. Filter out Shadow Nodes (Targets of POTENTIAL edges)
        # These nodes exist for static analysis but should not be executed.
        shadow_ids = {
            edge.target.id for edge in graph.edges if edge.edge_type == EdgeType.POTENTIAL
        }
        active_nodes = [node for node in graph.nodes if node.id not in shadow_ids]

        # 1. Calculate in-degrees for all active nodes
        in_degree: Dict[str, int] = {node.id: 0 for node in active_nodes}
        adj_list: Dict[str, List[str]] = {node.id: [] for node in active_nodes}

        for edge in graph.edges:
            # Skip POTENTIAL edges and edges involving shadow nodes
            if edge.edge_type == EdgeType.POTENTIAL:
                continue
            if edge.source.id in shadow_ids or edge.target.id in shadow_ids:
                continue

            in_degree[edge.target.id] += 1
            adj_list[edge.source.id].append(edge.target.id)

        # 2. Identify initial layer (nodes with 0 in-degree)
        current_stage = [node for node in active_nodes if in_degree[node.id] == 0]

        # Sort stage by name for deterministic behavior
        current_stage.sort(key=lambda n: n.name)

        plan: ExecutionPlan = []
        processed_count = 0

        # Optimization lookup for active nodes
        node_lookup = {n.id: n for n in active_nodes}

        while current_stage:
            plan.append(current_stage)
            processed_count += len(current_stage)
            next_stage_nodes: Set[str] = set()

            # 3. Simulate execution of current stage
            for node in current_stage:
                # For each downstream neighbor
                for neighbor_id in adj_list[node.id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        next_stage_nodes.add(neighbor_id)

            # Prepare next stage
            next_stage = [node_lookup[nid] for nid in next_stage_nodes]
            next_stage.sort(key=lambda n: n.name)  # Deterministic

            current_stage = next_stage

        # 4. Cycle detection
        if processed_count < len(active_nodes):
            # Finding the cycle is complex, for now raise a generic error
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        nodes = graph.nodes
        if not nodes:
            return []

        # 1. Preprocessing: Extract static resource requirements
        # node_id -> {resource_name: amount}
        node_resources: Dict[str, Dict[str, float]] = {}
        for node in nodes:
            reqs = {}
            if node.constraints:
                for res, amount in node.constraints.requirements.items():
                    # CSP currently only handles static constraints.
                    # Dynamic constraints (LazyResults) are treated as 0 usage during planning.
                    if not isinstance(amount, (LazyResult, MappedLazyResult)):
                        reqs[res] = float(amount)
            node_resources[node.id] = reqs

        # 2. Iterative Deepening Search
        # Try to find a schedule with K stages, starting from K=1 up to N (serial execution).
        # Optimization: Start K from the length of the critical path (longest dependency chain)
        # could be faster, but K=1 is a safe, simple start.

        n_nodes = len(nodes)
        solution = None

        # We try max_stages from 1 to n_nodes.
        # In the worst case (full serial), we need n_nodes stages.
        for max_stages in range(1, n_nodes + 1):
            solution = self._solve_csp(graph, node_resources, max_stages)
            if solution:
                break

        if not solution:
            raise RuntimeError(
                "CSPSolver failed to find a valid schedule. "
                "This usually implies circular dependencies or unsatisfiable resource constraints "
                "(e.g., a single task requires more resources than system total)."
            )

        # 3. Convert solution to ExecutionPlan
        # solution is {node_id: stage_index}
        plan_dict = defaultdict(list)
        for node_id, stage_idx in solution.items():
            plan_dict[stage_idx].append(node_id)

        # Sort stage indices
        sorted_stages = sorted(plan_dict.keys())

        # Build list of lists of Nodes
        node_lookup = {n.id: n for n in nodes}
        execution_plan = []

        for stage_idx in sorted_stages:
            node_ids = plan_dict[stage_idx]
            stage_nodes = [node_lookup[nid] for nid in node_ids]
            # Sort nodes in stage for determinism
            stage_nodes.sort(key=lambda n: n.name)
            execution_plan.append(stage_nodes)

        return execution_plan

    def _solve_csp(
        self, graph: Graph, node_resources: Dict[str, Dict[str, float]], max_stages: int
    ) -> Optional[Dict[str, int]]:
        problem = constraint.Problem()

        # Variables: Node IDs
        # Domain: Possible Stage Indices [0, max_stages - 1]
        domain = list(range(max_stages))
        variables = [n.id for n in graph.nodes]
        problem.addVariables(variables, domain)

        # Constraint 1: Dependencies
        # If A -> B, then stage(A) < stage(B)
        for edge in graph.edges:
            # Note: We use a lambda that captures nothing, args are passed by value in addConstraint
            problem.addConstraint(
                lambda s_src, s_tgt: s_src < s_tgt, (edge.source.id, edge.target.id)
            )

        # Constraint 2: Resources
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        from cascade.graph.model import EdgeType

        # 0. Filter out Shadow Nodes
        shadow_ids = {
            edge.target.id
            for edge in graph.edges
            if edge.edge_type == EdgeType.POTENTIAL
        }
        active_nodes = [node for node in graph.nodes if node.id not in shadow_ids]

        if not active_nodes:
            return []

        # 1. Preprocessing: Extract static resource requirements
        # node_id -> {resource_name: amount}
        node_resources: Dict[str, Dict[str, float]] = {}
        for node in active_nodes:
            reqs = {}
            if node.constraints:
                for res, amount in node.constraints.requirements.items():
                    # CSP currently only handles static constraints.
                    # Dynamic constraints (LazyResults) are treated as 0 usage during planning.
                    if not isinstance(amount, (LazyResult, MappedLazyResult)):
                        reqs[res] = float(amount)
            node_resources[node.id] = reqs

        # 2. Iterative Deepening Search
        # Try to find a schedule with K stages, starting from K=1 up to N (serial execution).
        # Optimization: Start K from the length of the critical path (longest dependency chain)
        # could be faster, but K=1 is a safe, simple start.

        n_nodes = len(active_nodes)
        solution = None

        # We try max_stages from 1 to n_nodes.
        # In the worst case (full serial), we need n_nodes stages.
        for max_stages in range(1, n_nodes + 1):
            solution = self._solve_csp(graph, active_nodes, shadow_ids, node_resources, max_stages)
            if solution:
                break

        if not solution:
            raise RuntimeError(
                "CSPSolver failed to find a valid schedule. "
                "This usually implies circular dependencies or unsatisfiable resource constraints "
                "(e.g., a single task requires more resources than system total)."
            )

        # 3. Convert solution to ExecutionPlan
        # solution is {node_id: stage_index}
        plan_dict = defaultdict(list)
        for node_id, stage_idx in solution.items():
            plan_dict[stage_idx].append(node_id)

        # Sort stage indices
        sorted_stages = sorted(plan_dict.keys())

        # Build list of lists of Nodes
        node_lookup = {n.id: n for n in active_nodes}
        execution_plan = []

        for stage_idx in sorted_stages:
            node_ids = plan_dict[stage_idx]
            stage_nodes = [node_lookup[nid] for nid in node_ids]
            # Sort nodes in stage for determinism
            stage_nodes.sort(key=lambda n: n.name)
            execution_plan.append(stage_nodes)

        return execution_plan

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

        # Variables: Node IDs (only active ones)
        # Domain: Possible Stage Indices [0, max_stages - 1]
        domain = list(range(max_stages))
        variables = [n.id for n in active_nodes]
        problem.addVariables(variables, domain)

        # Constraint 1: Dependencies
        # If A -> B, then stage(A) < stage(B)
        for edge in graph.edges:
            # Skip POTENTIAL edges and edges involving shadow nodes
            if edge.edge_type == EdgeType.POTENTIAL:
                continue
            if edge.source.id in shadow_ids or edge.target.id in shadow_ids:
                continue

            # Note: We use a lambda that captures nothing, args are passed by value in addConstraint
            problem.addConstraint(
                lambda s_src, s_tgt: s_src < s_tgt, (edge.source.id, edge.target.id)
            )

        # Constraint 2: Resources
~~~~~

#### Acts 2: 修正目标节点定位逻辑

修正 `GraphExecutionStrategy` 中的 `_update_graph_literals` 方法。我们将使用 `graph.nodes[0]` 来定位 Root 节点。这是基于 `GraphBuilder` Top-Down 构建过程的确定性事实。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        # ... logic moved from Engine ...
        if graph.nodes:
            target_node = graph.nodes[-1]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        # ... logic moved from Engine ...
        if graph.nodes:
            # FIX: Previously used nodes[-1], which became incorrect when shadow nodes
            # were appended to the end of the list by static analysis.
            # GraphBuilder uses a top-down approach (pre-order traversal), so the
            # root target node is always the FIRST node added to the graph.
            target_node = graph.nodes[0]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)
~~~~~

### 下一步建议
在这些修改应用后，`NativeSolver` 和 `GraphExecutionStrategy` 应该能正确处理包含影子节点的图。建议立即运行测试套件（特别是 `tests/engine/runtime/test_engine_recursion.py`）来验证修复效果。如果测试通过，我们就可以确信静态分析的引入不再干扰核心引擎的稳定性。
