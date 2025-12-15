from typing import Dict, Any, Set
from uuid import uuid4
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult, Task

class GraphBuilder:
    """
    Constructs a Graph from a target LazyResult by traversing dependencies.
    """
    def __init__(self):
        self.graph = Graph()
        # Map LazyResult UUID to created Node to ensure singularity (handle diamond deps)
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, result: LazyResult) -> Node:
        # If we already processed this specific LazyResult instance, return its Node
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # Create a new Node for this task execution
        node = Node(
            id=result._uuid,
            name=result.task.name,
            callable_obj=result.task.func
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Traverse inputs (args and kwargs) to find dependencies
        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)
        
        for key, value in iterator:
            arg_name = str(key) # key is int for args, str for kwargs
            
            if isinstance(value, LazyResult):
                # Found a dependency! Recurse.
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            
            # TODO: Handle lists/dicts containing LazyResults (Future MVP enhancement)

def build_graph(target: LazyResult) -> Graph:
    """Helper function to build a graph from a result."""
    return GraphBuilder().build(target)