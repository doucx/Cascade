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
