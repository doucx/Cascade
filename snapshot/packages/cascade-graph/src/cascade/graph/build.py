from typing import Dict, Any, Optional
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import analyze_task_source


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, scan_for_tco: bool = True) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # 1. Capture the structure of inputs
        literal_inputs = {str(i): v for i, v in enumerate(result.args)}
        literal_inputs.update(result.kwargs)

        # Pre-compute signature
        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        # 3. Handle conditionals
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        # 4. Handle dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name,
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        # 5. Handle explicit sequence dependencies
        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # Check cache on Task object to avoid re-parsing AST
            if getattr(result.task, "_potential_tco_targets", None) is None:
                result.task._potential_tco_targets = analyze_task_source(result.task.func)

            potential_targets = result.task._potential_tco_targets
            for target_task in potential_targets:
                potential_uuid = f"potential:{result._uuid}:{target_task.name}"
                
                shadow_lr = LazyResult(
                    task=target_task,
                    args=(),
                    kwargs={},
                    _uuid=potential_uuid
                )

                # Shadow nodes are created by directly instantiating Node,
                # not by visiting the LazyResult, to mark them explicitly.
                # This avoids them being added to the `_visited` cache with a real UUID.
                target_node = Node(
                    id=potential_uuid,
                    name=target_task.name,
                    node_type="task",
                    is_shadow=True,  # Explicitly mark as a shadow node
                )
                self.graph.add_node(target_node)
                self._visited[potential_uuid] = target_node
                
                edge = Edge(
                    source=node,
                    target=target_node,
                    arg_name="<potential>",
                    edge_type=EdgeType.POTENTIAL
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
            literal_inputs=result.mapping_kwargs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj)
            edge = Edge(
                source=source_node,
                target=target_node,
                arg_name=path or "dependency",
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

        elif isinstance(obj, Router):
            selector_node = self._visit(obj.selector)
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=f"{path}.selector" if path else "selector",
                router=obj,
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

            for route_key, route_result in obj.routes.items():
                route_node = self._visit(route_result)
                imp_edge = Edge(
                    source=route_node,
                    target=target_node,
                    arg_name=f"{path}.route[{route_key}]",
                    edge_type=EdgeType.ROUTER_ROUTE,
                )
                self.graph.add_edge(imp_edge)

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(
                    target_node, item, path=f"{path}[{i}]" if path else str(i)
                )

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(
                    target_node, v, path=f"{path}.{k}" if path else str(k)
                )


def build_graph(target: LazyResult) -> Graph:
    return GraphBuilder().build(target)