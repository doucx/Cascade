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