from collections import deque
from typing import Dict, List

from cascade.execution.graph.model.model import Graph, Node, EdgeType
from cascade.spec.runtime.interfaces import Solver, ExecutionPlan


class NativeSolver(Solver):
    def resolve(self, graph: Graph) -> ExecutionPlan:
        executable_nodes = graph.nodes

        adj: Dict[str, List[Node]] = {
            node.current_node_instance_hash: [] for node in executable_nodes
        }
        in_degree: Dict[str, int] = {
            node.current_node_instance_hash: 0 for node in executable_nodes
        }
        node_map: Dict[str, Node] = {
            node.current_node_instance_hash: node for node in executable_nodes
        }

        # Whitelist of edge types that represent actual execution dependencies.
        # This prevents metadata edges (like POTENTIAL) from creating cycles.
        EXECUTION_EDGE_TYPES = {
            EdgeType.DATA,
            EdgeType.CONDITION,
            EdgeType.CONSTRAINT,
            EdgeType.IMPLICIT,
            EdgeType.SEQUENCE,
            EdgeType.ROUTER_ROUTE,  # Considered a dependency for plan completeness
        }

        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            # Ensure edge connects executable nodes
            if (
                edge.source.current_node_instance_hash not in node_map
                or edge.target.current_node_instance_hash not in node_map
            ):
                continue

            adj[edge.source.current_node_instance_hash].append(edge.target)
            in_degree[edge.target.current_node_instance_hash] += 1

        # Kahn's algorithm for topological sorting
        queue = deque(
            [
                node.current_node_instance_hash
                for node in executable_nodes
                if in_degree[node.current_node_instance_hash] == 0
            ]
        )
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
                    in_degree[neighbor_node.current_node_instance_hash] -= 1
                    if in_degree[neighbor_node.current_node_instance_hash] == 0:
                        queue.append(neighbor_node.current_node_instance_hash)

        # If not all nodes were processed, a cycle must exist.
        if processed_count != len(executable_nodes):
            raise ValueError("Cycle detected in the dependency graph.")

        return plan
