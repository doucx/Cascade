from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router). This class is
    stateless; all state is read from and written to a StateBackend instance.
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id
        
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)
                
                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # Note: Demand counting for pruning is now handled dynamically based on
        # the state within the StateBackend, not pre-calculated.

    def _get_obj_id(self, obj: Any) -> str:
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        return str(obj)

    def register_result(self, node_id: str, result: Any, state_backend: StateBackend):
        """
        Notifies FlowManager of a task completion. 
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                self._process_router_decision(edge_with_router, result, state_backend)

    def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_id = self._get_obj_id(route_lazy_result)
                # This branch is NOT selected. Mark it to be pruned.
                state_backend.mark_skipped(branch_root_id, "Pruned_UnselectedRoute")

    def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := state_backend.get_skip_reason(node.id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not state_backend.has_result(edge.source.id):
                    # Propagate skip if condition source was skipped
                    if state_backend.get_skip_reason(edge.source.id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"
                
                condition_result = state_backend.get_result(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
        
        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            if state_backend.has_result(selector_id):
                active_route_key = state_backend.get_result(selector_id)

        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.id].get(edge.source.id)
                    if edge_key != active_route_key:
                        continue
                
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Route"
            
            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Data"
        
        return None