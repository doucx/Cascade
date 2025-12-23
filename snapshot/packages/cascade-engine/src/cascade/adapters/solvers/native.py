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

        # Whitelist of edge types that represent actual execution dependencies.
        # This prevents metadata edges (like POTENTIAL) from creating cycles.
        EXECUTION_EDGE_TYPES = {
            EdgeType.DATA,
            EdgeType.CONDITION,
            EdgeType.CONSTRAINT,
            EdgeType.IMPLICIT,
            EdgeType.SEQUENCE,
            EdgeType.ROUTER_ROUTE, # Considered a dependency for plan completeness
        }

        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
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