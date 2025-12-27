from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()

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

        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)

        if not node:
            # Extract bindings
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            sig = None
            if result.task.func:
                try:
                    sig = inspect.signature(result.task.func)
                except (ValueError, TypeError):
                    pass

            # Robustly determine complexity to enable FAST PATH in ArgumentResolver
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False

            # 1. Check for Runtime Context Injection (Special internal tasks)
            if result.task.func is _get_param_value.func:
                has_complex = True

            # 2. Check for Implicit Injection in Signature Defaults
            if not has_complex and sig:
                has_complex = any(
                    isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                )

            # 3. Check for Explicit Injection in Bindings (recursively)
            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                structural_id=structural_hash,
                name=result.task.name,
                node_type="task",
                execution_mode=result.task.mode,
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        # 4. Finalize edges (idempotent)
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        # 4.1 Handle Explicit Jump Binding
        if result._jump_selector:
            selector = result._jump_selector
            if isinstance(selector, JumpSelector):
                # Ensure all potential targets in the selector are built/visited
                for route_target in selector.routes.values():
                    if route_target is not None:
                        self._visit(route_target)

                # Create a distinct ITERATIVE_JUMP edge for each potential jump target.
                # This makes the static graph correctly represent all potential control flows.
                for key, route_target_lr in selector.routes.items():
                    if route_target_lr is None:
                        continue  # Skip exit routes, as they don't form an edge

                    # We have already visited the target, so it's in the instance map
                    target_node = self._visited_instances[route_target_lr._uuid]

                    self.graph.add_edge(
                        Edge(
                            source=node,
                            target=target_node,
                            arg_name=key,  # Use the jump key as the edge label
                            edge_type=EdgeType.ITERATIVE_JUMP,
                            # We can still attach the selector for the engine's use
                            jump_selector=selector,
                        )
                    )

        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        if result._constraints:
            for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=source,
                            target=node,
                            arg_name=res,
                            edge_type=EdgeType.CONSTRAINT,
                        )
                    )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. Post-order traversal for mapped inputs
        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.mapping_kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            return Node(
                structural_id=structural_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph
        self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name=path or "dep",
                    edge_type=EdgeType.DATA,
                )
            )

        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(
                Edge(
                    source=selector_node,
                    target=target_node,
                    arg_name=path,
                    router=obj,
                    edge_type=EdgeType.DATA,
                )
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
                self._scan_and_add_edges(
                    target_node, item, path=f"{path}[{i}]" if path else str(i)
                )

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(
                    target_node, v, path=f"{path}.{k}" if path else str(k)
                )


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
