import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError


class ArgumentResolver:
    """
    Responsible for resolving the actual arguments (args, kwargs) for a node execution
    from the graph structure, upstream results, and resource context.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers)
        3. Injected resources
        4. User provided params (for internal input tasks)

        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        # Local import to avoid circular dependency with internal.inputs -> spec.task -> runtime
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
        positional_args = {
            int(k): v for k, v in node.literal_inputs.items() if k.isdigit()
        }

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        for edge in incoming_edges:
            # Only process edges that carry data to the task (DATA edges)
            if edge.edge_type != EdgeType.DATA:
                continue

            # Resolve Upstream Value
            if edge.router:
                # Handle Dynamic Routing
                selector_value = upstream_results.get(edge.source.id)
                if selector_value is None:
                    # If the selector itself is missing, that's an error
                    if edge.source.id not in upstream_results:
                        raise DependencyMissingError(
                            node.id, "router_selector", edge.source.id
                        )

                try:
                    selected_lazy_result = edge.router.routes[selector_value]
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_value}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )

                dependency_id = selected_lazy_result._uuid
            else:
                # Standard dependency
                dependency_id = edge.source.id

            # Check existence in results
            if dependency_id not in upstream_results:
                raise DependencyMissingError(node.id, edge.arg_name, dependency_id)

            result = upstream_results[dependency_id]

            # Assign to args/kwargs
            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        # 2. Prepare arguments from injected resources (Implicit Injection via Signature)
        if node.callable_obj:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    resource_name = param.default.resource_name
                    if resource_name in resource_context:
                        final_kwargs[param.name] = resource_context[resource_name]
                    else:
                        raise NameError(
                            f"Task '{node.name}' requires resource '{resource_name}' "
                            "which was not found in the active context."
                        )

        # 3. Resolve explicit Inject objects in arguments (passed as values)
        # Convert positional map to list
        sorted_indices = sorted(positional_args.keys())
        args = [positional_args[i] for i in sorted_indices]

        resolved_args = []
        for arg in args:
            if isinstance(arg, Inject):
                if arg.resource_name in resource_context:
                    resolved_args.append(resource_context[arg.resource_name])
                else:
                    raise NameError(f"Resource '{arg.resource_name}' not found.")
            else:
                resolved_args.append(arg)
        args = resolved_args

        for key, value in final_kwargs.items():
            if isinstance(value, Inject):
                if value.resource_name in resource_context:
                    final_kwargs[key] = resource_context[value.resource_name]
                else:
                    raise NameError(f"Resource '{value.resource_name}' not found.")

        return args, final_kwargs


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
        
        # Find all CONSTRAINT edges relevant to this node
        constraint_edges = [
            e for e in graph.edges 
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        # Use the constraints requirements defined in the node spec as the primary source
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                # Match requirement name with the edge's arg_name (which is the resource name in GraphBuilder)
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
                
                if constraint_edge is None:
                    raise RuntimeError(
                        f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                    )

                if constraint_edge.source.id in upstream_results:
                    resolved[res] = upstream_results[constraint_edge.source.id]
                else:
                    raise DependencyMissingError(
                        node.id, f"constraint:{res}", constraint_edge.source.id
                    )
            else:
                resolved[res] = amount
        return resolved