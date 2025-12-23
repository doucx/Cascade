import inspect
from typing import Any, Dict, List, Tuple, Optional

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.binding import SlotRef, Constant
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (SlotRefs pointing to DataTuple)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        data_tuple: Tuple[Any, ...],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Special handling for internal param fetcher
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            # For params, we construct a synthetic kwargs dict
            # We assume the 'name' and 'default' are passed via bindings/data
            # but getting them from bindings logic below is cleaner.
            pass 

        # 1. Reconstruct initial args/kwargs from Bindings + DataTuple
        # This replaces the old 'literal_inputs' traversal
        initial_kwargs = {}
        positional_args_dict = {}

        for name, binding in node.input_bindings.items():
            value = self._resolve_binding(binding, data_tuple)
            
            # Recursively resolve structure (lists/dicts containing other things)
            # Note: In the new builder, complex structures are mostly flattened or kept as data.
            # If data contains LazyResults (which shouldn't happen for bindings), we'd need to resolve them.
            # But LazyResults are now Edges. 
            # However, nested lists/dicts might still exist in data. 
            # For now, we assume data is 'literal' enough, or we apply structure resolution.
            value = self._resolve_structure(value, node.id, state_backend, resource_context, graph)

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                initial_kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]
        kwargs = initial_kwargs

        # 2. Overlay Dependencies (Edges)
        # Edges overwrite bindings if they share the same arg_name (which they shouldn't usually, but precedence rules apply)
        # Actually, in the new model, an arg is EITHER a binding OR an edge.
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(edge, node.id, state_backend, graph)
                
                # Handle positional vs keyword
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    # Extend args list if needed
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    # Handle nested paths? e.g. "data.items[0]"
                    # For V3 Great Split, we simplify: top-level args only for now.
                    # Complex nested injection requires a more sophisticated setter.
                    # Assuming flat arg names for MVP.
                    kwargs[edge.arg_name] = val
            
            elif edge.edge_type == EdgeType.ROUTER_ROUTE:
                 # Implicitly handled via flow pruning, but if it carries data?
                 # Router edges are conditional paths. The actual data comes from the route result.
                 pass

        # 3. Handle Resource Injection (Defaults)
        # Only check params that are NOT already filled
        if node.signature:
            for param in node.signature.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in kwargs and (len(args) <= list(node.signature.parameters).index(param.name)):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
        elif node.callable_obj:
             sig = inspect.signature(node.callable_obj)
             for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                     if param.name not in kwargs: # Simplified check
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        # 4. Handle internal param fetching context
        if node.callable_obj is _get_param_value.func:
             kwargs["params_context"] = user_params or {}

        return args, kwargs

    def _resolve_binding(self, binding: Any, data_tuple: Tuple[Any, ...]) -> Any:
        if isinstance(binding, SlotRef):
            return data_tuple[binding.index]
        elif isinstance(binding, Constant):
            return binding.value
        # Fallback for legacy or raw values (shouldn't happen in strict mode)
        return binding

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        """
        Recursively traverses data structures.
        Mainly to handle Inject if it ended up in data, or nested lists/dicts.
        """
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
        edge: Any, # Typed as Edge, avoiding circular import
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        source_id = edge.source.id
        
        # If result exists, return it.
        if state_backend.has_result(source_id):
            return state_backend.get_result(source_id)

        # If missing, check skip logic (penetration, etc.)
        # Logic similar to old _resolve_lazy
        if state_backend.get_skip_reason(source_id):
             # Try penetration
             # Find inputs to the skipped source node
             upstream_edges = [e for e in graph.edges if e.target.id == source_id]
             data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
             
             if data_inputs:
                 # Recursively try to resolve the source of the skipped node
                 return self._resolve_dependency(data_inputs[0], consumer_id, state_backend, graph)
        
        skip_info = ""
        if reason := state_backend.get_skip_reason(source_id):
            skip_info = f" (skipped: {reason})"

        raise DependencyMissingError(
            consumer_id, edge.arg_name, f"{source_id}{skip_info}"
        )

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]

        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)