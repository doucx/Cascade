from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.spec.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            self.downstream_demand[edge.source.id] += 1

            if edge.router:
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1

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
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                # Note: In the Router model, the "edge" carrying the router implies a demand
                # from the consumer (edge.target) to the route (branch_root).
                # Since we decided NOT to use this route, that demand is effectively gone.
                self._decrement_demand_and_prune(branch_root_id, state_backend)

    def _decrement_demand_and_prune(self, node_id: str, state_backend: StateBackend):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned
        and recursively processes its upstreams.
        """
        # If already skipped/pruned, no need to do anything further
        if state_backend.get_skip_reason(node_id):
            return

        self.downstream_demand[node_id] -= 1

        if self.downstream_demand[node_id] <= 0:
            state_backend.mark_skipped(node_id, "Pruned")

            # Recursively reduce demand for inputs of the pruned node
            for edge in self.in_edges[node_id]:
                # Special case: If the edge is from a Router, do we prune the Router selector?
                # No, the selector might be used by other branches.
                # Standard dependency logic applies: reduce demand on source.
                self._decrement_demand_and_prune(edge.source.id, state_backend)

    def should_skip(self, node: Node, state_backend: StateBackend) -> Optional[str]:
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
