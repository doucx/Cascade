import inspect
from typing import Any, Dict
from cascade.graph.model import Graph, Node
from cascade.spec.resource import Inject


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    async def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from dependency results and injected resources.
        """
        # 1. Prepare arguments from all sources
        # Literals are the base
        final_kwargs = {
            k: v for k, v in node.literal_inputs.items() if not k.isdigit()
        }
        positional_args = {
            int(k): v for k, v in node.literal_inputs.items() if k.isdigit()
        }

        # Upstream results override literals
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            # Skip control flow edges
            if edge.arg_name == "_condition":
                continue
            
            # Skip implicit dependencies (used for routing/ordering only)
            if edge.arg_name == "_implicit_dependency":
                continue

            result = upstream_results[edge.source.id]
            
            # Handle Dynamic Routing
            if edge.router:
                # 'result' is the value of the selector (e.g., "csv")
                selector_value = result
                try:
                    selected_lazy_result = edge.router.routes[selector_value]
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_value}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )
                
                # Retrieve the actual result of the selected task
                actual_value = upstream_results[selected_lazy_result._uuid]
                
                if edge.arg_name.isdigit():
                    positional_args[int(edge.arg_name)] = actual_value
                else:
                    final_kwargs[edge.arg_name] = actual_value
            else:
                # Standard dependency
                if edge.arg_name.isdigit():
                    positional_args[int(edge.arg_name)] = result
                else:
                    final_kwargs[edge.arg_name] = result

        sorted_indices = sorted(positional_args.keys())
        args = [positional_args[i] for i in sorted_indices]

        # A param node has no callable, so it shouldn't be executed
        if node.callable_obj is None:
            # This should not be reached due to Engine's skip, but as a safeguard:
            raise TypeError(f"Node '{node.name}' of type '{node.node_type}' is not executable.")

        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
            if isinstance(param.default, Inject):
                resource_name = param.default.resource_name
                if resource_name in resource_context:
                    kwargs_from_resources[param.name] = resource_context[resource_name]
                else:
                    raise NameError(
                        f"Task '{node.name}' requires resource '{resource_name}' "
                        "which was not found in the active context."
                    )

        # 3. Combine arguments and execute
        # Injected resources take precedence over other inputs
        final_kwargs = {**final_kwargs, **kwargs_from_resources}

        if inspect.iscoroutinefunction(node.callable_obj):
            return await node.callable_obj(*args, **final_kwargs)
        else:
            return node.callable_obj(*args, **final_kwargs)
