from typing import Dict, Any, List, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef

from .hashing import ShallowHasher
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
        self.hasher = ShallowHasher()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _create_node_from_lazy_result(
        self, result: LazyResult, node_id: str
    ) -> Node:
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

        # 1. Post-order traversal: Visit children FIRST
        child_edges: List[Tuple[Node, str, EdgeType, Any]] = []

        def visit_child(obj: Any, path: str, edge_type: EdgeType = EdgeType.DATA, meta: Any = None):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                node = self._visit(obj)
                child_edges.append((node, path, edge_type, meta))
            elif isinstance(obj, Router):
                sel_node = self._visit(obj.selector)
                child_edges.append((sel_node, path, edge_type, obj))
                for k, route_res in obj.routes.items():
                    r_node = self._visit(route_res)
                    child_edges.append((r_node, f"{path}.route[{k}]", EdgeType.ROUTER_ROUTE, None))
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    visit_child(item, f"{path}[{i}]" if path else str(i), edge_type, meta)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    visit_child(v, f"{path}.{k}" if path else str(k), edge_type, meta)
        
        for i, val in enumerate(result.args):
            visit_child(val, str(i))
        
        # Sort kwargs keys to ensure deterministic traversal order
        for k in sorted(result.kwargs.keys()):
            val = result.kwargs[k]
            visit_child(val, k)
        
        if result._condition:
            visit_child(result._condition, "_condition", EdgeType.CONDITION)
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                 if isinstance(req, (LazyResult, MappedLazyResult)):
                     visit_child(req, res, EdgeType.CONSTRAINT)
        for dep in result._dependencies:
             visit_child(dep, "<sequence>", EdgeType.SEQUENCE)

        # 2. Compute Structural ID (Fast Hash)
        # We use Python's built-in hash() which is faster than sha256.
        # CRITICAL: We MUST include result._uuid to distinguish different instances
        # of the same task in a sequence (e.g. [a(), a()]).
        # This sacrifices "Automatic Structural Deduping" for "Instance Correctness".
        shell_hash = self.hasher.hash(result)
        
        # Combine shell, UUID, and children IDs
        # We use a tuple to hash, which is very efficient in Python
        
        # CRITICAL: Sort child hashes to ensure deterministic Node ID regardless of 
        # dictionary iteration order (e.g. kwargs). This is vital for correct graph structure.
        # However, for 'args' (positional), order matters.
        # 'child_edges' is currently built by iterating args then kwargs.
        # Since 'args' order is significant but 'kwargs' key order is sorted by the visitor,
        # relying on list order is generally safe IF the visitor guarantees sorted kwargs.
        
        # Let's verify the visitor logic:
        # for i, val in enumerate(result.args): ... (Ordered)
        # for k, val in result.kwargs.items(): ... (Dict insertion order in Py3.7+, but let's be safe)
        
        # To be absolutely robust, we should trust the 'path' in child_edges to carry the order info.
        # So sorting child_hashes by path is safe and correct.
        
        # Sort by path to ensure deterministic hashing
        child_hashes = tuple(sorted(
            ((c.id, path, etype) for c, path, etype, _ in child_edges),
            key=lambda x: x[1] # Sort by arg path
        ))
        
        # The node_hash uniquely identifies this specific instance in the graph
        node_hash_int = hash((shell_hash, result._uuid, child_hashes))
        # Convert to string for ID compatibility
        node_hash = f"{node_hash_int:x}"

        # 3. Create or Get Canonical Node
        node_factory = lambda: self._create_node_from_lazy_result(result, node_hash)
        node, created_new = self.registry.get_or_create(node_hash, node_factory)

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
            
            for child, path, etype, meta in child_edges:
                edge = Edge(source=child, target=node, arg_name=path, edge_type=etype)
                if etype == EdgeType.DATA and meta:
                     edge.router = meta
                self.graph.add_edge(edge)

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
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]
            
        shallow_hash = self.hasher.hash(result) 
        # append UUID to prevent collisions
        node_hash_int = hash((shallow_hash, result._uuid))
        unique_hash = f"{node_hash_int:x}"

        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=unique_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(unique_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
        
        def scan(obj, path):
             if isinstance(obj, (LazyResult, MappedLazyResult)):
                 src = self._visit(obj)
                 self.graph.add_edge(Edge(source=src, target=node, arg_name=path, edge_type=EdgeType.DATA))
             elif isinstance(obj, list):
                 for i, x in enumerate(obj): scan(x, f"{path}[{i}]")
        
        for k, v in result.mapping_kwargs.items():
            scan(v, k)

        return node


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)