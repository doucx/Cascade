from typing import List, Dict, Set
from collections import deque, defaultdict

from cascade.spec.ir.models import GraphIR
from cascade.compiler.exceptions import CycleDetectedError

# ExecutionPlan is defined as a list of stages, where each stage is a list of Node IDs
ExecutionPlan = List[List[str]]


class Optimizer:
    """
    Compiler Optimizer: Transforms a GraphIR into a scheduled ExecutionPlan.
    """

    @staticmethod
    def optimize(graph: GraphIR) -> ExecutionPlan:
        """
        Performs topological sort on the GraphIR to produce an execution schedule.

        Args:
            graph: The Intermediate Representation of the compute graph.

        Returns:
            A list of stages, where each stage contains a list of Node IDs that
            can be executed in parallel.

        Raises:
            CycleDetectedError: If the graph contains a dependency cycle.
        """
        # 1. Initialize data structures
        # Adjacency list: source_id -> list of target_ids
        adj: Dict[str, List[str]] = defaultdict(list)
        # In-degree: node_id -> count
        in_degree: Dict[str, int] = {
            node.current_node_instance_hash: 0 for node in graph.nodes
        }

        # 2. Build graph topology from IR edges
        for edge in graph.edges:
            # Check if nodes exist (sanity check, though IR should be valid)
            if (
                edge.source_node_instance_hash not in in_degree
                or edge.target_node_instance_hash not in in_degree
            ):
                continue

            adj[edge.source_node_instance_hash].append(edge.target_node_instance_hash)
            in_degree[edge.target_node_instance_hash] += 1

        # 3. Kahn's Algorithm
        # Initial queue: nodes with in-degree 0
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        plan: ExecutionPlan = []
        processed_count = 0
        total_nodes = len(graph.nodes)

        while queue:
            # Snapshot current queue as the current stage
            # All nodes in this stage depend only on nodes from previous stages
            current_stage_ids = list(queue)

            # Sort for deterministic output (crucial for testing and reproducibility)
            current_stage_ids.sort()

            plan.append(current_stage_ids)
            processed_count += len(current_stage_ids)

            # Clear queue for the next iteration (we process stage by stage)
            queue.clear()

            # Process neighbors
            for node_id in current_stage_ids:
                for neighbor_id in adj[node_id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        queue.append(neighbor_id)

        # 4. Cycle Detection
        if processed_count != total_nodes:
            raise CycleDetectedError(
                f"Cycle detected in dependency graph. Processed {processed_count}/{total_nodes} nodes."
            )

        return plan
