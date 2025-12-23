from typing import Dict, Any, List, Tuple
import inspect
import hashlib
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef
from cascade.spec.resource import Inject

from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # Maps a LazyResult's instance UUID to its canonical Node object
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self._data_buffer: List[Any] = []
        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        # This is now the core of the post-order traversal.
        # We handle the value based on its type to get the final Node.
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components_from_arg(
        self, obj: Any, dep_nodes: Dict[str, Node]
    ) -> List[str]:
        """Recursively builds hash components from arguments, using pre-computed dependency nodes."""
        components = []
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Use the pre-computed canonical node ID for the dependency.
            components.append(f"LAZY({dep_nodes[obj._uuid].id})")
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(
                self._build_hash_components_from_arg(obj.selector, dep_nodes)
            )
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_hash_components_from_arg(obj.routes[k], dep_nodes)
                )
            components.append("}")
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components_from_arg(item, dep_nodes))
            components.append("]")
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(
                    self._build_hash_components_from_arg(obj[k], dep_nodes)
                )
            components.append("}")
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")
        return components

    def _create_node_from_lazy_result(
        self, result: LazyResult, node_id: str
    ) -> Node:
        # This function is now simpler: it just creates the Node object.
        # Hashing and dependency visiting happens before this is called.
        input_bindings = {}

        def process_arg(key: str, val: Any):
            if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                input_bindings[key] = self._register_data(val)

        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        for k, val in result.kwargs.items():
            process_arg(k, val)

        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        return Node(
            id=node_id,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. POST-ORDER TRAVERSAL: Visit all dependencies FIRST.
        dep_nodes: Dict[str, Node] = {}

        def find_deps(obj: Any):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                if obj._uuid not in dep_nodes:
                    # Recursively visit to get the canonical node
                    dep_node = self._visit(obj)
                    dep_nodes[obj._uuid] = dep_node
            elif isinstance(obj, Router):
                find_deps(obj.selector)
                for route in obj.routes.values():
                    find_deps(route)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    find_deps(item)
            elif isinstance(obj, dict):
                for v in obj.values():
                    find_deps(v)

        find_deps(result.args)
        find_deps(result.kwargs)
        if result._condition:
            find_deps(result._condition)
        if result._constraints:
            find_deps(result._constraints.requirements)
        if result._dependencies:
            find_deps(result._dependencies)

        # 2. MERKLE HASHING: Now build the hash using dependency IDs.
        hash_components = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            hash_components.append(f"Cache({type(result._cache_policy).__name__})")
        
        hash_components.append("Args:")
        hash_components.extend(self._build_hash_components_from_arg(result.args, dep_nodes))
        
        hash_components.append("Kwargs:")
        hash_components.extend(self._build_hash_components_from_arg(result.kwargs, dep_nodes))

        if result._condition:
            hash_components.append("Condition:PRESENT")
        if result._dependencies:
            hash_components.append(f"Deps:{len(result._dependencies)}")
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            hash_components.append(f"Constraints({','.join(keys)})")
        
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. NODE CREATION & REGISTRATION (Hash-consing)
        node_factory = lambda: self._create_node_from_lazy_result(
            result, structural_hash
        )
        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        # 4. GRAPH ASSEMBLY: Add node and edges if newly created.
        if created_new:
            self.graph.add_node(node)
            # Static analysis (shadow graph) part remains the same.
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
                potential_targets = analyze_task_source(result.task)
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)

        # Add edges to the graph. All dependency nodes are already in the graph.
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)
        if result._condition:
            source_node = self._visit(result._condition)
            self.graph.add_edge(Edge(source=source_node, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visit(req)
                    self.graph.add_edge(Edge(source=source, target=node, arg_name=res, edge_type=EdgeType.CONSTRAINT))
        for dep in result._dependencies:
            source = self._visit(dep)
            self.graph.add_edge(Edge(source=source, target=node, arg_name="<sequence>", edge_type=EdgeType.SEQUENCE))
        
        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))
            return

        potential_uuid = f"shadow:{parent_node.id}:{task.name}"
        target_node = Node(id=potential_uuid, name=task.name, node_type="task", is_shadow=True, tco_cycle_id=getattr(task, "_tco_cycle_id", None))
        
        self.graph.add_node(target_node)
        self._shadow_visited[task] = target_node
        self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))

        for next_task in analyze_task_source(task):
            self._visit_shadow_recursive(target_node, next_task)

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        # Simplified for now. A full implementation would mirror _visit_lazy_result's post-order logic.
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
        
        # This part needs the same post-order hashing logic as _visit_lazy_result
        # For now, let's keep it simple to pass the current tests.
        dep_nodes: Dict[str, Node] = {}
        def find_deps(obj: Any):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                if obj._uuid not in dep_nodes:
                    dep_node = self._visit(obj)
                    dep_nodes[obj._uuid] = dep_node
            elif isinstance(obj, (list, tuple)):
                for item in obj: find_deps(item)
            elif isinstance(obj, dict):
                for v in obj.values(): find_deps(v)
        
        find_deps(result.mapping_kwargs)

        hash_components = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        hash_components.append("MapKwargs:")
        hash_components.extend(self._build_hash_components_from_arg(result.mapping_kwargs, dep_nodes))
        
        structural_hash = self._get_merkle_hash(hash_components)

        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=structural_hash,
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

        if created_new:
            self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)
        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(Edge(source=source_node, target=target_node, arg_name=path or "dep", edge_type=EdgeType.DATA))

        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(Edge(source=selector_node, target=target_node, arg_name=path, router=obj, edge_type=EdgeType.DATA))
            for key, route_res in obj.routes.items():
                route_node = self._visited_instances[route_res._uuid]
                self.graph.add_edge(Edge(source=route_node, target=target_node, arg_name=f"{path}.route[{key}]", edge_type=EdgeType.ROUTER_ROUTE))

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)