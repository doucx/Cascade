from typing import Dict, List, Set
from cascade.spec.model import Graph
from cascade.interfaces.protocols import ExecutionPlan


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
