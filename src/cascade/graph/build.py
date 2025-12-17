from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        # Target could be a MappedLazyResult too
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

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
            constraints=result._constraints,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.task import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    # Use EdgeType.CONSTRAINT instead of magic arg_name prefix
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name, # Use resource name as arg_name
                        edge_type=EdgeType.CONSTRAINT
                    )
                    self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Process dependencies in mapping_kwargs
        # Note: These arguments are treated as kwargs
        self._process_dependencies(node, result.mapping_kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, MappedLazyResult)):
                source_node = self._visit(value)
                # Standard DATA edge
                edge = Edge(
                    source=source_node, 
                    target=target_node, 
                    arg_name=arg_name, 
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
                # Edge for the Router selector is a DATA edge that happens to carry Router metadata
                edge = Edge(
                    source=selector_node,
                    target=target_node,
                    arg_name=arg_name,
                    router=value,
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)

                for route_key, route_result in value.routes.items():
                    route_node = self._visit(route_result)
                    # Specific edge type for Router routes, allowing dynamic pruning later
                    imp_edge = Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"_route_{route_key}", 
                        edge_type=EdgeType.ROUTER_ROUTE
                    )
                    self.graph.add_edge(imp_edge)
            else:
                target_node.literal_inputs[arg_name] = value


def build_graph(target: LazyResult) -> Graph:
    """Helper function to build a graph from a result."""
    return GraphBuilder().build(target)