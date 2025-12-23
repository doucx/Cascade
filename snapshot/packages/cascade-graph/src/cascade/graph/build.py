from typing import Dict, Any, List, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef
from .registry import NodeRegistry


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # Maps a LazyResult's instance UUID to its canonical Node object
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}
        self._data_buffer: List[Any] = []
        # The registry is now simpler, just a check for node existence in the graph
        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
        if isinstance(value, (LazyResult, MappedLazyResult)):
            # Check if this specific instance has been visited
            if value._uuid in self._visited_instances:
                return self._visited_instances[value._uuid]

            # Create a new node for this instance
            if isinstance(value, LazyResult):
                node = self._create_node_from_lazy_result(value)
            else:
                node = self._create_node_from_mapped_result(value)

            # Register and process children
            self._visited_instances[value._uuid] = node
            self.graph.add_node(node)
            self._process_children(node, value)
            return node
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _create_node_from_lazy_result(self, result: LazyResult) -> Node:
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
            id=result._uuid,  # CRITICAL CHANGE: Node ID is now instance UUID
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )
        
    def _create_node_from_mapped_result(self, result: MappedLazyResult) -> Node:
        input_bindings = {}
        for k, val in result.mapping_kwargs.items():
            if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                input_bindings[k] = self._register_data(val)
        
        return Node(
            id=result._uuid, # CRITICAL CHANGE
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )

    def _process_children(self, parent_node: Node, result: Any):
        # This unified function handles adding edges for all child types
        
        def visit_child(obj: Any, path: str, edge_type: EdgeType = EdgeType.DATA, meta: Any = None):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                child_node = self._visit(obj)
                edge = Edge(source=child_node, target=parent_node, arg_name=path, edge_type=edge_type)
                if meta: edge.router = meta
                self.graph.add_edge(edge)
            elif isinstance(obj, Router):
                visit_child(obj.selector, path, EdgeType.DATA, obj) # Pass router as meta
                for k, route_res in obj.routes.items():
                    visit_child(route_res, f"{path}.route[{k}]", EdgeType.ROUTER_ROUTE)
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    visit_child(item, f"{path}[{i}]" if path else str(i))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    visit_child(v, f"{path}.{k}" if path else str(k))

        # Scan args/kwargs
        args_source = result.args if isinstance(result, LazyResult) else ()
        kwargs_source = result.kwargs if isinstance(result, LazyResult) else result.mapping_kwargs

        for i, val in enumerate(args_source):
            visit_child(val, str(i))
        for k, val in kwargs_source.items():
            visit_child(val, k)
            
        # Scan special dependencies
        if result._condition:
            visit_child(result._condition, "_condition", EdgeType.CONDITION)
        if result._constraints:
             for res, req in result._constraints.requirements.items():
                 if isinstance(req, (LazyResult, MappedLazyResult)):
                     visit_child(req, res, EdgeType.CONSTRAINT)
        for dep in result._dependencies:
             visit_child(dep, "<sequence>", EdgeType.SEQUENCE)

        # Static Analysis (only for LazyResult with a real task)
        if isinstance(result, LazyResult) and result.task.func:
            if not getattr(result.task, "_tco_analysis_done", False):
                assign_tco_cycle_ids(result.task)
            parent_node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
            
            potential_targets = analyze_task_source(result.task)
            self._shadow_visited[result.task] = parent_node
            for target_task in potential_targets:
                self._visit_shadow_recursive(parent_node, target_task)

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))
            return

        potential_id = f"shadow:{parent_node.id}:{task.name}"
        target_node = Node(id=potential_id, name=task.name, node_type="task", is_shadow=True, tco_cycle_id=getattr(task, "_tco_cycle_id", None))
        
        self.graph.add_node(target_node)
        self._shadow_visited[task] = target_node
        self.graph.add_edge(Edge(source=parent_node, target=target_node, arg_name="<potential>", edge_type=EdgeType.POTENTIAL))

        for next_task in analyze_task_source(task):
            self._visit_shadow_recursive(target_node, next_task)

def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)