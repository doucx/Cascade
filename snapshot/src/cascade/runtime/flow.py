from typing import Dict, Any, Optional, Set, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id
        self._skipped_nodes: Set[str] = set()
        
        # --- 1. Build Topology Indices ---
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                # Map selector_id -> edges that utilize this selector
                selector_id = edge.router.selector._uuid
                self.routers_by_selector[selector_id].append(edge)

        # --- 2. Initialize Reference Counting (Demand) ---
        # A node's initial demand is its out-degree (number of consumers).
        # We also treat the final workflow target as having +1 implicit demand.
        self.downstream_demand: Dict[str, int] = defaultdict(int)
        
        for edge in self.graph.edges:
            self.downstream_demand[edge.source.id] += 1
            
        self.downstream_demand[target_node_id] += 1

    def mark_skipped(self, node_id: str, reason: str = "Unknown"):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)
        # Note: We don't decrement demand here because if a node is skipped naturally 
        # (e.g. condition false), its downstream will handle "UpstreamSkipped".
        # Pruning is a proactive measure for nodes that haven't run yet.

    def is_skipped(self, node_id: str) -> bool:
        return node_id in self._skipped_nodes

    def register_result(self, node_id: str, result: Any):
        """
        Notify FlowManager of a task completion. 
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                self._process_router_decision(edge_with_router, result)

    def _process_router_decision(self, edge: Edge, selector_value: Any):
        router = edge.router
        
        # 1. Identify unselected routes
        # Selector value might be non-hashable, but route keys in dict usually are strings/ints.
        # We rely on simple equality check.
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key == selected_route_key:
                continue
                
            # This route is NOT selected.
            # The edge from this route branch to the target node is logically "broken".
            # We decrement the demand for the branch's root node.
            branch_root_id = route_lazy_result._uuid
            self._decrement_demand_and_prune(branch_root_id)

    def _decrement_demand_and_prune(self, node_id: str):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned 
        and recursively processes its upstreams.
        """
        if self.is_skipped(node_id):
            return

        self.downstream_demand[node_id] -= 1
        
        if self.downstream_demand[node_id] <= 0:
            # No one needs this node anymore. Prune it!
            # But wait, we should check if it has already run?
            # Engine handles that check (it won't check should_skip for completed nodes).
            self.mark_skipped(node_id, reason="Pruned")
            
            # Recursively decrement demand for its UPSTREAM dependencies.
            # These are the sources of incoming edges.
            for edge in self.in_edges[node_id]:
                self._decrement_demand_and_prune(edge.source.id)

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 0. Check if already marked (e.g. Pruned)
        if self.is_skipped(node.id):
            return "Pruned"

        # 1. Upstream Skip Propagation (Cascade Skip)
        for edge in self.in_edges[node.id]:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT, EdgeType.ROUTER_ROUTE):
                if self.is_skipped(edge.source.id):
                    return "UpstreamSkipped"

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if edge.source.id not in results:
                    return "ConditionMissing"
                
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None