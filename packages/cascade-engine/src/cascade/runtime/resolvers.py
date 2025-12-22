import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by traversing the structure stored in node.literal_inputs
    and replacing LazyResult/Router/Inject placeholders with actual values.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Special handling for internal param fetcher
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # Recursively resolve the structure, passing the graph for context
        resolved_structure = self._resolve_structure(
            node.literal_inputs, node.id, state_backend, resource_context, graph
        )

        # Re-assemble args and kwargs
        final_kwargs = {k: v for k, v in resolved_structure.items() if not k.isdigit()}
        positional_args_dict = {
            int(k): v for k, v in resolved_structure.items() if k.isdigit()
        }

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # Handle Inject in defaults (if not overridden by inputs)
        if node.signature:
            for param in node.signature.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
        elif node.callable_obj:
            # Fallback if signature wasn't cached for some reason
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        return args, final_kwargs

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        """
        Recursively traverses lists, tuples, and dicts.
        Replaces LazyResult, Router, and Inject.
        """
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            return self._resolve_lazy(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Router):
            return self._resolve_router(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Inject):
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

    def _resolve_lazy(
        self,
        lr: LazyResult,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        # If result exists, return it immediately.
        if state_backend.has_result(lr._uuid):
            return state_backend.get_result(lr._uuid)

        # If it doesn't exist, check if it was skipped.
        if state_backend.get_skip_reason(lr._uuid):
            # Attempt data penetration ONLY for pipeline-like structures.
            # We look for a DATA input to the skipped node.

            # Find the edges leading into the skipped node
            upstream_edges = [e for e in graph.edges if e.target.id == lr._uuid]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]

            if data_inputs:
                # Prioritize the first DATA input for penetration.
                # This is a simplification but correct for linear pipelines.
                penetration_source_id = data_inputs[0].source.id

                # Create a temporary LazyResult to recursively resolve the penetrated source.
                # We pass the original consumer_id down.
                penetration_lr_stub = LazyResult(
                    task=None, args=(), kwargs={}, _uuid=penetration_source_id
                )
                try:
                    # If this succeeds, we have successfully penetrated the skipped node.
                    return self._resolve_lazy(
                        penetration_lr_stub, consumer_id, state_backend, graph
                    )
                except DependencyMissingError:
                    # If the penetrated source is ALSO missing, we must fail.
                    # This will fall through to the final DependencyMissingError.
                    pass

        # If not skipped, or if skipped but penetration failed/was not applicable, raise an error.
        # This now correctly handles the test_run_if_false case.
        skip_info = ""
        if reason := state_backend.get_skip_reason(lr._uuid):
            skip_info = f" (skipped: {reason})"

        raise DependencyMissingError(
            consumer_id, "unknown_arg", f"{lr._uuid}{skip_info}"
        )

    def _resolve_router(
        self,
        router: Router,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        # 1. Resolve Selector
        selector_uuid = router.selector._uuid
        if not state_backend.has_result(selector_uuid):
            raise DependencyMissingError(consumer_id, "router_selector", selector_uuid)

        selector_value = state_backend.get_result(selector_uuid)

        # 2. Pick Route
        try:
            selected_lr = router.routes[selector_value]
        except KeyError:
            raise ValueError(
                f"Router selector returned '{selector_value}', "
                f"but no matching route found in {list(router.routes.keys())}"
            )

        # 3. Resolve Route Result
        return self._resolve_lazy(selected_lr, consumer_id, state_backend, graph)

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
        constraint_manager: Any = None,
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    if state_backend.has_result(amount._uuid):
                        resolved[res] = state_backend.get_result(amount._uuid)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
