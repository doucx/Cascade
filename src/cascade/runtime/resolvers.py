import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph
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
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers)
        3. Injected resources
        
        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
        positional_args = {
            int(k): v for k, v in node.literal_inputs.items() if k.isdigit()
        }

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"): # Skip control/meta edges
                continue
            
            # Resolve Upstream Value
            if edge.router:
                # Handle Dynamic Routing
                selector_value = upstream_results.get(edge.source.id)
                if selector_value is None:
                     # If the selector itself is missing, that's an error
                     if edge.source.id not in upstream_results:
                         raise DependencyMissingError(node.id, "router_selector", edge.source.id)
                
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
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}
        
        resolved = {}
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                if amount._uuid in upstream_results:
                    resolved[res] = upstream_results[amount._uuid]
                else:
                    # Logic to determine if it was skipped or just missing
                    raise DependencyMissingError(node.id, f"constraint:{res}", amount._uuid)
            else:
                resolved[res] = amount
        return resolved