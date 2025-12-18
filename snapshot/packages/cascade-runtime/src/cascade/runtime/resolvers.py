import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.interfaces.spec.resource import Inject
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.protocols import StateBackend


class ArgumentResolver:
    """
    Responsible for resolving the actual arguments (args, kwargs) for a node execution
    from the graph structure, upstream results, and resource context.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers) from the state backend
        3. Injected resources
        4. User provided params (for internal input tasks)

        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
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
            if edge.edge_type != EdgeType.DATA:
                continue

            dependency_id: str
            if edge.router:
                selector_result = state_backend.get_result(edge.source.id)
                if selector_result is None:
                    if not state_backend.has_result(edge.source.id):
                        raise DependencyMissingError(
                            node.id, "router_selector", edge.source.id
                        )

                try:
                    selected_lazy_result = edge.router.routes[selector_result]
                    dependency_id = selected_lazy_result._uuid
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_result}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )
            else:
                dependency_id = edge.source.id

            if not state_backend.has_result(dependency_id):
                raise DependencyMissingError(node.id, edge.arg_name, dependency_id)

            result = state_backend.get_result(dependency_id)

            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        # 2. Prepare arguments from injected resources
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
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
        
        constraint_edges = [
            e for e in graph.edges 
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
                
                if constraint_edge is None:
                    raise RuntimeError(
                        f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                    )

                if state_backend.has_result(constraint_edge.source.id):
                    resolved[res] = state_backend.get_result(constraint_edge.source.id)
                else:
                    raise DependencyMissingError(
                        node.id, f"constraint:{res}", constraint_edge.source.id
                    )
            else:
                resolved[res] = amount
        return resolved