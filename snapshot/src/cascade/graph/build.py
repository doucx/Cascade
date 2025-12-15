from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit_lazy_result(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, Param):
            return self._visit_param(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_param(self, param: Param) -> Node:
        # Use param name as its unique ID
        if param.name in self._visited:
            return self._visited[param.name]

        node = Node(
            id=param.name,
            name=param.name,
            node_type="param",
            param_spec=param,
        )
        self.graph.add_node(node)
        self._visited[param.name] = node
        return node

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, Param)):
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
                edge = Edge(
                    source=selector_node, 
                    target=target_node, 
                    arg_name=arg_name,
                    router=value
                )
                self.graph.add_edge(edge)
                
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    imp_edge = Edge(
                        source=route_node, 
                        target=target_node, 
                        arg_name="_implicit_dependency"
                    )
                    self.graph.add_edge(imp_edge)
            else:
                target_node.literal_inputs[arg_name] = value

            # TODO: Handle lists/dicts containing LazyResults (Future MVP enhancement)


def build_graph(target: LazyResult) -> Graph:
    """Helper function to build a graph from a result."""
    return GraphBuilder().build(target)
