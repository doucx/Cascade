import inspect
from typing import Any, Dict
from cascade.graph.model import Graph, Node
from cascade.spec.resource import Inject


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    def execute(
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
        # 1. Prepare arguments from upstream task results
        kwargs_from_deps: Dict[str, Any] = {}
        positional_args_from_deps = {}

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args_from_deps[int(edge.arg_name)] = result
            else:
                kwargs_from_deps[edge.arg_name] = result

        sorted_indices = sorted(positional_args_from_deps.keys())
        args = [positional_args_from_deps[i] for i in sorted_indices]

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
        # Dependencies take precedence over resource injections if names conflict
        final_kwargs = {**kwargs_from_resources, **kwargs_from_deps}

        return node.callable_obj(*args, **final_kwargs)
