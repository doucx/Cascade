简要回答：
我们将通过引入“迭代深度搜索 (Iterative Deepening Search)”策略来实现 `CSPSolver`。这将确保求解器不仅能找到满足资源约束的可行解，还能找到阶段数最少（即并行度最高）的最优解。

## [WIP] feat(solver): 实现基于 CSP 的资源感知调度器

### 用户需求
实现 `CSPSolver.resolve` 方法，使其能够：
1.  将计算图转换为约束满足问题 (CSP)。
2.  强制执行任务间的依赖关系（下游任务的阶段索引必须大于上游）。
3.  强制执行全局资源约束（任意阶段内的任务资源总和不得超过系统容量）。
4.  通过迭代搜索找到 Makespan 最小（阶段数最少）的执行计划。

### 评论
这是 `Cascade` 迈向高级调度能力的关键一步。不同于朴素的拓扑排序，CSP 求解器能够在构建阶段就“预见”运行时的资源瓶颈，并自动将互斥的任务串行化。虽然引入了计算开销，但对于资源密集型工作流来说，这是避免运行时死锁和提高资源利用率的必要代价。

### 目标
1.  在 `cascade.adapters.solvers.csp` 中完善 `CSPSolver` 类。
2.  实现静态资源需求的提取逻辑。
3.  实现基于 `python-constraint` 的约束建模和求解逻辑。
4.  编写单元测试验证资源冲突时的自动串行化行为。

### 基本原理
我们采用“迭代深度搜索”策略：从 $K=1$ 开始尝试限制总阶段数，逐步增加 $K$ 直到找到第一个可行解。这个 $K$ 值即为最短的 Makespan。这比单纯寻找任意可行解更能保证执行效率。对于资源约束，我们使用 CSP 的全局约束能力，检查分配给同一阶段索引的所有任务的资源总和。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/solver #scope/core #ai/instruct #task/domain/core #task/object/csp-solver #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 `CSPSolver` 核心逻辑

我们将修改 `csp.py`，实现 `resolve` 方法。核心逻辑包括：
1.  预处理：提取节点资源需求，构建 ID 映射。
2.  迭代搜索：从 1 到 N (节点数) 尝试 `max_stages`。
3.  CSP 建模：定义变量（节点），域（0 到 max_stages-1），依赖约束和资源约束。
4.  结果转换：将 CSP 解（节点->阶段索引）转换为 `ExecutionPlan`（阶段列表）。

~~~~~act
write_file
src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
from typing import Dict, List, Any, Optional
from collections import defaultdict
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan
from cascade.spec.lazy_types import LazyResult, MappedLazyResult

try:
    import constraint
except ImportError:
    constraint = None


class CSPSolver:
    """
    A solver that uses Constraint Satisfaction Problem (CSP) techniques to produce
    a resource-aware execution plan.
    
    It employs Iterative Deepening Search to find the schedule with the minimum
    number of stages (Makespan) that satisfies all dependency and resource constraints.
    """

    def __init__(self, system_resources: Dict[str, float]):
        """
        Args:
            system_resources: A dictionary defining the total available capacity 
                              for each resource (e.g., {"gpu": 2, "memory_gb": 32}).
        """
        if constraint is None:
            raise ImportError(
                "The 'python-constraint' library is required to use the CSPSolver. "
                "Please install it with: pip install cascade-py[csp_solver]"
            )
        self.system_resources = system_resources

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
        self, 
        graph: Graph, 
        node_resources: Dict[str, Dict[str, float]], 
        max_stages: int
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
                lambda s_src, s_tgt: s_src < s_tgt, 
                (edge.source.id, edge.target.id)
            )
            
        # Constraint 2: Resources
        # Sum of resources in each stage <= system_resources
        if self.system_resources:
            # We define a constraint function that accepts the stage assignment for ALL nodes
            def resource_check(*stage_assignments):
                # Reconstruct the stage -> nodes mapping for this assignment attempt
                stages = defaultdict(list)
                for i, stage_idx in enumerate(stage_assignments):
                    node_id = variables[i] # variables list order matches args order
                    stages[stage_idx].append(node_id)
                
                # Check each stage
                for stage_nodes in stages.values():
                    stage_usage = defaultdict(float)
                    for nid in stage_nodes:
                        for res, amount in node_resources[nid].items():
                            stage_usage[res] += amount
                    
                    # Verify against system limits
                    for res, limit in self.system_resources.items():
                        if stage_usage[res] > limit:
                            return False
                return True

            problem.addConstraint(resource_check, variables)
            
        return problem.getSolution()
~~~~~

#### Acts 2: 编写测试用例

我们将在 `tests/adapters/solvers/test_csp.py` 中添加两个关键测试：
1.  **资源充足场景**: 两个无依赖任务，资源充足，应并行执行（1个阶段）。
2.  **资源不足场景**: 两个无依赖任务，每个需要 60% 资源，系统只有 100%，应自动串行执行（2个阶段）。

~~~~~act
write_file
tests/adapters/solvers/test_csp.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.csp import CSPSolver

# Skip tests if python-constraint is not installed
pytest.importorskip("constraint")


def test_csp_solver_init():
    """Test that CSPSolver can be initialized with resources."""
    solver = CSPSolver(system_resources={"cpu": 4, "ram": 16})
    assert solver.system_resources == {"cpu": 4, "ram": 16}


def test_csp_solver_missing_dependency(monkeypatch):
    """Test that meaningful error is raised if dependency is missing."""
    import cascade.adapters.solvers.csp as csp_module
    
    # Simulate missing dependency by setting constraint to None
    monkeypatch.setattr(csp_module, "constraint", None)
    
    with pytest.raises(ImportError, match="python-constraint"):
        CSPSolver(system_resources={})


def test_csp_solver_parallel_when_resources_sufficient():
    """
    Scenario: System has 10 CPU.
    Task A needs 4 CPU.
    Task B needs 4 CPU.
    No dependencies.
    
    Expected: Both run in Stage 0 (Parallel).
    """
    @task
    def t_a(): pass

    @task
    def t_b(): pass
    
    @task
    def gather(a, b): pass

    # Construct graph: A and B feed into Gather
    # But we want to test scheduling of A and B. 
    # Let's just create a dummy gather to build the graph.
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)
    
    graph = build_graph(target)
    
    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)
    
    # Analyze plan
    # Gather depends on A and B, so Gather must be later.
    # A and B depend on nothing.
    
    # We expect minimum 2 stages: [A, B], [Gather]
    # Because A(4) + B(4) = 8 <= 10, they fit in one stage.
    
    assert len(plan) == 2
    
    first_stage_names = {n.name for n in plan[0]}
    assert "t_a" in first_stage_names
    assert "t_b" in first_stage_names
    assert len(plan[0]) == 2


def test_csp_solver_serial_when_resources_insufficient():
    """
    Scenario: System has 6 CPU.
    Task A needs 4 CPU.
    Task B needs 4 CPU.
    No dependencies.
    
    Expected: Run in separate stages (Serial) to respect limit.
    Plan should be 3 stages: [A], [B], [Gather] OR [B], [A], [Gather].
    """
    @task
    def t_a(): pass

    @task
    def t_b(): pass
    
    @task
    def gather(a, b): pass

    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)
    
    graph = build_graph(target)
    
    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
    plan = solver.resolve(graph)
    
    # A(4) + B(4) = 8 > 6. Cannot run in parallel.
    # Must be split.
    # Gather is dependent on both, so it comes last.
    # Total stages should be 3.
    
    assert len(plan) == 3
    
    stage_0_names = {n.name for n in plan[0]}
    stage_1_names = {n.name for n in plan[1]}
    
    # One of them is in stage 0, the other in stage 1
    assert len(plan[0]) == 1
    assert len(plan[1]) == 1
    
    # Verify content
    assert stage_0_names.union(stage_1_names) == {"t_a", "t_b"}
    assert plan[2][0].name == "gather"
~~~~~
