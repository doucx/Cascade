from typing import Dict, Any, List, Tuple
import inspect
import hashlib
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.resource import Inject

from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
        """Central dispatcher for the post-order traversal."""
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
            # Hash-Consing: The identity of this dependency is its structural ID.
            components.append(f"LAZY({dep_nodes[obj._uuid].id})")
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components_from_arg(obj.selector, dep_nodes))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components_from_arg(obj.routes[k], dep_nodes))
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
                components.extend(self._build_hash_components_from_arg(obj[k], dep_nodes))
            components.append("}")
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")
        return components

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
        """Helper for post-order traversal: finds and visits all nested LazyResults."""
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

        # 2. Compute structural Merkle hash
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

        # 3. Hash-consing: intern the Node object
        def node_factory():
            input_bindings = {}
            def process_arg(key: str, val: Any):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    # Store literal value directly
                    input_bindings[key] = val

            for i, val in enumerate(result.args):
                process_arg(str(i), val)
            for k, val in result.kwargs.items():
                process_arg(k, val)

            sig = None
            if result.task.func:
                try: sig = inspect.signature(result.task.func)
                except (ValueError, TypeError): pass

            return Node(
                id=structural_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
                potential_targets = analyze_task_source(result.task)
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)

        # 4. Finalize edges (idempotent)
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)
        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(Edge(source=source_node, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(Edge(source=source, target=node, arg_name=res, edge_type=EdgeType.CONSTRAINT))
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="<sequence>", edge_type=EdgeType.SEQUENCE))
        
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

        # 2. Compute structural hash for Map node
        hash_components = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        hash_components.append("MapKwargs:")
        hash_components.extend(self._build_hash_components_from_arg(result.mapping_kwargs, dep_nodes))
        
        if result._condition: hash_components.append("Condition:PRESENT")
        if result._dependencies: hash_components.append(f"Deps:{len(result._dependencies)}")
        
        structural_hash = self._get_merkle_hash(hash_components)

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val
            
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

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(Edge(source=source, target=node, arg_name="_condition", edge_type=EdgeType.CONDITION))
        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
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

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        """Idempotently adds DATA and ROUTER edges based on pre-visited instances."""
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
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)