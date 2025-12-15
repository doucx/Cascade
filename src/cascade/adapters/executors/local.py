from typing import Any, Dict, List
from cascade.graph.model import Graph, Node

class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """
    def execute(
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any]
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from the results of its dependencies.
        """
        # Find all edges that point to the current node
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # Prepare arguments
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}
        
        # This is a simplified approach assuming we know the number of positional args
        # A more robust solution might inspect the function signature.
        # For now, we assume args are sorted by their integer `arg_name`.
        
        positional_args = {}
        
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                # It's a positional argument, store with its index
                positional_args[int(edge.arg_name)] = result
            else:
                # It's a keyword argument
                kwargs[edge.arg_name] = result

        # Sort and create the final positional args list
        if positional_args:
            sorted_indices = sorted(positional_args.keys())
            args = [positional_args[i] for i in sorted_indices]

        # Execute the function
        return node.callable_obj(*args, **kwargs)