from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, Edge, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (Literal values stored in Node)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        positional_args_dict = {}
        for name, value_raw in node.input_bindings.items():
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(
                value_raw, node.id, state_backend, resource_context, graph
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]

        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(
                    edge, node.id, state_backend, graph, instance_map
                )

                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    kwargs[edge.arg_name] = val

        # 3. Handle Resource Injection in Defaults
        if node.signature:
            # Create a bound arguments object to see which args are not yet filled
            try:
                bound_args = node.signature.bind_partial(*args, **kwargs)
                for param in node.signature.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except TypeError:
                # This can happen if args/kwargs are not yet valid, but we can still try a simpler check
                pass

        # 4. Handle internal param fetching context
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}

        return args, kwargs

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        if isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)
        elif isinstance(obj, list):
            return [
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            ]
        elif isinstance(obj, tuple):
            return tuple(
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            )
        elif isinstance(obj, dict):
            return {
                k: self._resolve_structure(
                    v, consumer_id, state_backend, resource_context, graph
                )
                for k, v in obj.items()
            }
        return obj

    def _resolve_dependency(
        self,
        edge: Edge,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
        instance_map: Dict[str, Node],
    ) -> Any:
        # ** CORE ROUTER LOGIC FIX **
        if edge.router:
            # This edge represents a Router. Its source is the SELECTOR.
            # We must resolve the selector's value first.
            selector_result = self._get_node_result(
                edge.source.id, consumer_id, "router_selector", state_backend, graph
            )

            # Use the result to pick the correct route.
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )

            # Now, resolve the result of the SELECTED route.
            # Convert instance UUID to canonical node ID using the map.
            selected_node = instance_map[selected_route_lr._uuid]
            return self._get_node_result(
                selected_node.id, consumer_id, edge.arg_name, state_backend, graph
            )
        else:
            # Standard dependency
            return self._get_node_result(
                edge.source.id, consumer_id, edge.arg_name, state_backend, graph
            )

    def _get_node_result(
        self,
        node_id: str,
        consumer_id: str,
        arg_name: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        """Helper to get a node's result, with skip penetration logic."""
        if state_backend.has_result(node_id):
            return state_backend.get_result(node_id)

        if state_backend.get_skip_reason(node_id):
            upstream_edges = [e for e in graph.edges if e.target.id == node_id]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
            if data_inputs:
                # Recursively try to penetrate the skipped node
                return self._get_node_result(
                    data_inputs[0].source.id,
                    consumer_id,
                    arg_name,
                    state_backend,
                    graph,
                )

        skip_info = (
            f" (skipped: {state_backend.get_skip_reason(node_id)})"
            if state_backend.get_skip_reason(node_id)
            else ""
        )
        raise DependencyMissingError(consumer_id, arg_name, f"{node_id}{skip_info}")

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]
        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any,
        instance_map: Dict[str, Node],
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    # Get the canonical node for the dynamic constraint value
                    constraint_node = instance_map.get(amount._uuid)
                    if not constraint_node:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )

                    if state_backend.has_result(constraint_node.id):
                        resolved[res] = state_backend.get_result(constraint_node.id)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", constraint_node.id
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
