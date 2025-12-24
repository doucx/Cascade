from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(
        self, graph: Graph, target_node_id: str, instance_map: Dict[str, Node]
    ):
        self.graph = graph
        self.target_node_id = target_node_id
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.structural_id].append(edge)
            self.downstream_demand[edge.source.structural_id] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.structural_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.structural_id][
                            route_node.structural_id
                        ] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1

    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        elif isinstance(instance, Param):
            # Find the node that represents this param
            for node in self.graph.nodes:
                if node.param_spec and node.param_spec.name == instance.name:
                    return node
        return None

    async def register_result(
        self, node_id: str, result: Any, state_backend: StateBackend
    ):
        """
        Notifies FlowManager of a task completion.
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                await self._process_router_decision(
                    edge_with_router, result, state_backend
                )

    async def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value

        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_node = self._get_node_from_instance(route_lazy_result)
                if not branch_root_node:
                    continue  # Should not happen in a well-formed graph
                branch_root_id = branch_root_node.structural_id
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                await self._decrement_demand_and_prune(branch_root_id, state_backend)

    async def _decrement_demand_and_prune(
        self, node_id: str, state_backend: StateBackend
    ):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned
        and recursively processes its upstreams.
        """
        # If already skipped/pruned, no need to do anything further
        if await state_backend.get_skip_reason(node_id):
            return

        self.downstream_demand[node_id] -= 1

        if self.downstream_demand[node_id] <= 0:
            await state_backend.mark_skipped(node_id, "Pruned")

            # Recursively reduce demand for inputs of the pruned node
            for edge in self.in_edges[node_id]:
                # Special case: If the edge is from a Router, do we prune the Router selector?
                # No, the selector might be used by other branches.
                # Standard dependency logic applies: reduce demand on source.
                await self._decrement_demand_and_prune(
                    edge.source.structural_id, state_backend
                )

    async def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := await state_backend.get_skip_reason(node.structural_id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not await state_backend.has_result(edge.source.structural_id):
                    if await state_backend.get_skip_reason(edge.source.structural_id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"

                condition_result = await state_backend.get_result(
                    edge.source.structural_id
                )
                if not condition_result:
                    return "ConditionFalse"

            # New explicit check for sequence abortion
            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next(
            (e for e in self.in_edges[node.structural_id] if e.router), None
        )
        if router_edge:
            selector_node = self._get_node_from_instance(router_edge.router.selector)
            if selector_node:
                selector_id = selector_node.structural_id
                if await state_backend.has_result(selector_id):
                    active_route_key = await state_backend.get_result(selector_id)

        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.structural_id].get(
                        edge.source.structural_id
                    )
                    if edge_key != active_route_key:
                        continue

                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Route"

            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    # Check for data penetration possibility (for pipelines)
                    can_penetrate = False
                    # Look for inputs to the skipped node (edge.source)
                    for upstream_edge in self.in_edges[edge.source.structural_id]:
                        # If the skipped node has a DATA input, and that input has a result...
                        if (
                            upstream_edge.edge_type == EdgeType.DATA
                            and await state_backend.has_result(
                                upstream_edge.source.structural_id
                            )
                        ):
                            can_penetrate = True
                            break

                    if not can_penetrate:
                        return "UpstreamSkipped_Data"
                    # If it can penetrate, we don't return a skip reason.
                    # We let the node proceed to execution, where ArgumentResolver will handle it.

            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        return None
