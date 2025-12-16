from typing import Dict, Any, Optional, Set, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult


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
        
        # Mapping: consumer_id -> { source_node_id -> route_key }
        # Used to identify which route key a ROUTER_ROUTE edge corresponds to.
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                # Map selector_id -> edges that utilize this selector
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)
                
                # Build the route source map for the consumer (edge.target)
                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # --- 2. Initialize Reference Counting (Demand) ---
        # A node's initial demand is its out-degree (number of consumers).
        # We also treat the final workflow target as having +1 implicit demand.
        self.downstream_demand: Dict[str, int] = defaultdict(int)
        
        for edge in self.graph.edges:
            self.downstream_demand[edge.source.id] += 1
            
        self.downstream_demand[target_node_id] += 1

    def _get_obj_id(self, obj: Any) -> str:
        """Helper to get ID from LazyResult or Param."""
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        # Fallback, though graph building should ensure these types
        return str(obj)

    def mark_skipped(self, node_id: str, reason: str = "Unknown"):
        """Manually marks a node as skipped."""
        self._skipped_nodes.add(node_id)

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
        
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key == selected_route_key:
                continue
                
            # This route is NOT selected. Prune it.
            branch_root_id = self._get_obj_id(route_lazy_result)
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
            self.mark_skipped(node_id, reason="Pruned")
            
            for edge in self.in_edges[node_id]:
                self._decrement_demand_and_prune(edge.source.id)

    def should_skip(
        self, node: Node, results: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        if self.is_skipped(node.id):
            return "Pruned"

        # Determine active route key if this node is a Router consumer
        active_route_key = None
        # Find the edge carrying the Router definition
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            # If selector result is available, we know the active key
            if selector_id in results:
                active_route_key = results[selector_id]
            # If selector is missing/skipped, we can't determine active key yet.
            # But standard DATA dependency check below will handle missing selector.

        # 1. Upstream Skip Propagation
        for edge in self.in_edges[node.id]:
            # Special handling for ROUTER_ROUTE edges
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                # If we know the active route, we only care about that one.
                if active_route_key is not None:
                    # Look up which key this edge corresponds to
                    edge_key = self.route_source_map[node.id].get(edge.source.id)
                    # If this edge is NOT the active route, ignore its skip status
                    if edge_key != active_route_key:
                        continue
                
                # If active_route_key is unknown (shouldn't happen if selector ran),
                # or if this IS the active route, check if it's skipped.
                if self.is_skipped(edge.source.id):
                    return "UpstreamSkipped"

            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
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