from typing import Dict, Any, Optional, Set, List
from cascade.graph.model import Node, Graph, EdgeType
from cascade.runtime.exceptions import DependencyMissingError


class FlowManager:
    """
    Manages the control flow of the execution, determining which tasks
    should be skipped based on conditions (run_if) or routing logic (Router).
    """

    def __init__(self, graph: Graph):
        self.graph = graph
        self._skipped_nodes: Set[str] = set()

    def mark_skipped(self, node_id: str):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)

    def is_skipped(self, node_id: str) -> bool:
        return node_id in self._skipped_nodes

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Upstream Skip Propagation (Cascade Skip)
        # Check DATA, IMPLICIT, and ROUTER_ROUTE edges
        incoming_edges = [edge for edge in self.graph.edges if edge.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT, EdgeType.ROUTER_ROUTE):
                # If an upstream dependency was skipped, we must skip this node too.
                # Note: For Router, if the *selected* branch was skipped, we skip.
                # Pruning logic (skipping unselected branches) handles the other case 
                # before we get here.
                if edge.source.id in self._skipped_nodes:
                    return "UpstreamSkipped"

        # 2. Condition Check (run_if)
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.CONDITION:
                if edge.source.id not in results:
                    # Condition task didn't run? Should be caught by UpstreamSkipped,
                    # but double check safety.
                    return "ConditionMissing"
                
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None