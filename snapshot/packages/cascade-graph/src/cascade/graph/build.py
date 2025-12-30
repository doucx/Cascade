from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import (
    Graph,
    Node,
    Edge,
    EdgeType,
    TaskNode,
    MapNode,
    ParamNode,
)
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService
from .analysis.reflection import ReflectionAnalyzer


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        self._visited_instances: Dict[str, Node] = {}
        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
        self.analyzer = ReflectionAnalyzer()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            if obj._uuid not in dep_nodes:
                dep_node = self._visit(obj)
                dep_nodes[obj._uuid] = dep_node
        elif isinstance(obj, Router):
            self._find_dependencies(obj.selector, dep_nodes)
            for route in obj.routes.values():
                self._find_dependencies(route, dep_nodes)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._find_dependencies(item, dep_nodes)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._find_dependencies(v, dep_nodes)

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. Post-order: Resolve all dependencies first
        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.args, dep_nodes)
        self._find_dependencies(result.kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._constraints:
            self._find_dependencies(result._constraints.requirements, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # 2. Analyze Code to get TaskDef
        task_def = self.analyzer.analyze(result.task)

        # 3. Compute Node Instance Hash
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(node_hash)
        if not node:
            # This is where we decide which Node subclass to instantiate
            if result._param_spec:
                node = ParamNode(
                    structural_id=node_hash,
                    param_spec=result._param_spec,
                    definition=task_def,
                    callable_obj=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                )
            else:
                # Standard TaskNode
                input_bindings = {}
                for i, val in enumerate(result.args):
                    if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                        input_bindings[str(i)] = val
                for k, val in result.kwargs.items():
                    if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                        input_bindings[k] = val

                has_complex = self._has_complex_inputs(result, input_bindings)

                node = TaskNode(
                    structural_id=node_hash,
                    definition=task_def,
                    callable_obj=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry.register(node_hash, node)

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        # 5. Edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        if result._jump_selector:
            self._add_jump_edges(node, result._jump_selector)
        if result._condition:
            self._add_metadata_edge(node, result._condition, EdgeType.CONDITION)
        if result._constraints:
            self._add_constraint_edges(node, result._constraints)
        if result._dependencies:
            for dep in result._dependencies:
                self._add_metadata_edge(node, dep, EdgeType.SEQUENCE)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.mapping_kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        task_def = self.analyzer.analyze(result.factory)
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(node_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = MapNode(
                structural_id=node_hash,
                definition=task_def,
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry.register(node_hash, node)

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            self._add_metadata_edge(node, result._condition, EdgeType.CONDITION)
        for dep in result._dependencies:
            self._add_metadata_edge(node, dep, EdgeType.SEQUENCE)

        return node

    def _has_complex_inputs(self, result: LazyResult, bindings: Dict[str, Any]) -> bool:
        from cascade.spec.resource import Inject as InjectMarker

        if any(isinstance(p.default, InjectMarker) for p in result.task._signature.parameters.values()):
            return True

        def is_complex_value(v):
            if isinstance(v, InjectMarker):
                return True
            if isinstance(v, (list, tuple)):
                return any(is_complex_value(x) for x in v)
            if isinstance(v, dict):
                return any(is_complex_value(x) for x in v.values())
            return False

        return any(is_complex_value(v) for v in bindings.values())

    def _add_metadata_edge(self, target: Node, source_lr: Any, edge_type: EdgeType):
        source_node = self._visited_instances[source_lr._uuid]
        self.graph.add_edge(
            Edge(source=source_node, target=target, arg_name=f"_{edge_type.name.lower()}", edge_type=edge_type)
        )

    def _add_constraint_edges(self, target: Node, constraints: Any):
        for res, req in constraints.requirements.items():
            if isinstance(req, (LazyResult, MappedLazyResult)):
                source = self._visited_instances[req._uuid]
                self.graph.add_edge(
                    Edge(source=source, target=target, arg_name=res, edge_type=EdgeType.CONSTRAINT)
                )

    def _add_jump_edges(self, source_node: Node, selector: JumpSelector):
        for route_target_lr in selector.routes.values():
            if route_target_lr:
                # Ensure the route target has been visited and is in the graph
                self._visit(route_target_lr)
                target_node = self._visited_instances[route_target_lr._uuid]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name="<jump>",
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector,
                    )
                )
    
    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(
                Edge(source=source_node, target=target_node, arg_name=path or "dep", edge_type=EdgeType.DATA)
            )
        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(
                Edge(source=selector_node, target=target_node, arg_name=path, router=obj, edge_type=EdgeType.DATA)
            )
            for key, route_res in obj.routes.items():
                route_node = self._visited_instances[route_res._uuid]
                self.graph.add_edge(
                    Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"{path}.route[{key}]",
                        edge_type=EdgeType.ROUTER_ROUTE,
                    )
                )
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))

def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)