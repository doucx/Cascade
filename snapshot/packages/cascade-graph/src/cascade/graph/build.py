from typing import Dict, Any, List, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import analyze_task_source, assign_tco_cycle_ids
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef, Constant


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}
        # Used to detect cycles during shadow node expansion
        self._shadow_visited: Dict[Task, Node] = {}
        
        # The meat: storage for extracted runtime data
        self._data_buffer: List[Any] = []

    def build(self, target: LazyResult) -> Tuple[Graph, Tuple[Any, ...]]:
        """
        Builds a GraphTemplate and extracts a DataTuple from the target LazyResult.
        
        Returns:
            (Graph, DataTuple): The pure topological structure and the flattened runtime data.
        """
        self._visit(target)
        return self.graph, tuple(self._data_buffer)

    def _register_data(self, value: Any) -> SlotRef:
        """Appends data to the buffer and returns a reference to its index."""
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

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

        # 1. Process Inputs: Separate Structure (Edges) from Data (Bindings)
        input_bindings = {}
        
        # Helper to process a single argument
        def process_arg(key: str, val: Any):
            # Recursion for nested structures (Lists/Dicts) containing LazyResults is not 
            # fully supported in this version of the builder for simplicity.
            # We assume top-level args are either LazyResult (Edge) or Data (Binding).
            # Complex nested structures should be handled by specific providers or flattened.
            
            if isinstance(val, (LazyResult, MappedLazyResult)):
                # It's a dependency, will be added as an Edge later
                pass 
            elif isinstance(val, Router):
                # Router is a structural construct, handled in edges
                pass
            else:
                # It's literal data, extract it!
                input_bindings[key] = self._register_data(val)

        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        
        for k, val in result.kwargs.items():
            process_arg(k, val)

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
            input_bindings=input_bindings, # Replaces literal_inputs
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges (Topology)
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
            # 6.1 Analyze and tag cycles if not already done
            if not getattr(result.task, "_tco_analysis_done", False):
                assign_tco_cycle_ids(result.task)
            
            # Propagate cycle ID to the Node
            node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

            # 6.2 Retrieve potential targets (using cache)
            potential_targets = analyze_task_source(result.task)
            
            # Register current node in shadow map to allow closing the loop back to root
            self._shadow_visited[result.task] = node

            for target_task in potential_targets:
                self._visit_shadow_recursive(node, target_task)

        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        """
        Recursively builds shadow nodes for static analysis.
        """
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            edge = Edge(
                source=parent_node,
                target=target_node,
                arg_name="<potential>",
                edge_type=EdgeType.POTENTIAL,
            )
            self.graph.add_edge(edge)
            return

        potential_uuid = f"shadow:{parent_node.id}:{task.name}"
        
        target_node = Node(
            id=potential_uuid,
            name=task.name,
            node_type="task",
            is_shadow=True,
            tco_cycle_id=getattr(task, "_tco_cycle_id", None)
        )
        self.graph.add_node(target_node)
        
        self._shadow_visited[task] = target_node

        edge = Edge(
            source=parent_node,
            target=target_node,
            arg_name="<potential>",
            edge_type=EdgeType.POTENTIAL,
        )
        self.graph.add_edge(edge)

        potential_targets = analyze_task_source(task)
        
        for next_task in potential_targets:
            self._visit_shadow_recursive(target_node, next_task)

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # Extract bindings for mapped inputs
        input_bindings = {}
        # Mapped inputs in mapping_kwargs are typically lists/iterables.
        # We treat the whole iterable as a single data unit for now.
        for k, val in result.mapping_kwargs.items():
            if not isinstance(val, (LazyResult, MappedLazyResult)):
                 input_bindings[k] = self._register_data(val)

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
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
            # The edge from the selector to the consumer represents the final resolved value
            # of the router. Its arg_name must be the argument the consumer expects for the router.
            selector_node = self._visit(obj.selector)
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=path,  # Use the router's own argument path
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


def build_graph(target: LazyResult) -> Tuple[Graph, Tuple[Any, ...]]:
    """
    Entry point for building a graph.
    
    Returns:
        (Graph, DataTuple)
    """
    return GraphBuilder().build(target)