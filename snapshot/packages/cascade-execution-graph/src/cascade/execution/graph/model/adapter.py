from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from cascade.compiler.frontend.generator import GenerationResult
from cascade.execution.graph.model.model import (
    Edge,
    EdgeType,
    Graph,
    MapNode,
    Node,
    ParamNode,
    TaskNode,
)
from cascade.execution.graph.model.registry import NodeRegistry
from cascade.spec.dsl.constraint import ResourceConstraint
from cascade.spec.dsl.fluent import RetryPolicy
from cascade.spec.dsl.jump import JumpSelector
from cascade.spec.dsl.routing import Router
from cascade.spec.ir.graph import NodeIR


@dataclass
class _StubLazyResult:
    _uuid: str


class IRToRuntimeAdapter:
    def __init__(self, registry: NodeRegistry | None = None):
        self.registry = registry or NodeRegistry()
        self.graph = Graph()
        # Maps node_instance_hash -> Runtime Node Object
        self.node_map: dict[str, Node] = {}
        # Maps logical_uuid (from IR) -> Runtime Node Object (for router reconstruction)
        self.logical_map: dict[str, Node] = {}

    def adapt(
        self, result: GenerationResult
    ) -> tuple[Graph, dict[str, Node], dict[str, Callable]]:
        ir = result.ir
        executables = result.executables

        # 1. Create Nodes
        for node_ir in ir.nodes:
            node = self._create_node(node_ir, executables)
            self.graph.add_node(node)
            self.node_map[node.current_node_instance_hash] = node
            if node_ir.logical_id:
                self.logical_map[node_ir.logical_id] = node

        # 2. Create Edges
        for node_ir in ir.nodes:
            target_node = self.node_map[node_ir.current_node_instance_hash]
            self._create_edges(node_ir, target_node)

        # 3. Create Instance Map (UUID -> Node) for FlowManager compatibility
        # Legacy runtime uses UUIDs for lookups in FlowManager
        instance_map: dict[str, Node] = {}
        for node_ir in ir.nodes:
            runtime_node = self.node_map[node_ir.current_node_instance_hash]

            # 1. Map Physical Hash -> Node (Used by FlowManager/Routers)
            instance_map[node_ir.current_node_instance_hash] = runtime_node

            # 2. Map Logical UUID -> Node (Used by External API / Legacy lookups)
            if node_ir.logical_id:
                instance_map[node_ir.logical_id] = runtime_node

        return self.graph, instance_map, executables

    def _is_dependency(self, value: Any) -> bool:
        return bool(isinstance(value, str) and value in self.node_map)

    def _create_node(self, node_ir: NodeIR, executables: dict[str, Callable]) -> Node:
        # Recover policies
        retry_policy = None
        if node_ir.retry_policy:
            retry_policy = RetryPolicy(
                max_attempts=node_ir.retry_policy["max_attempts"],
                delay=node_ir.retry_policy["delay"],
                backoff=node_ir.retry_policy["backoff"],
            )

        constraints = None
        if node_ir.constraints:
            constraints = ResourceConstraint(requirements=node_ir.constraints)

        # Input bindings: filter out router definitions and dependencies
        input_bindings = {}
        has_complex_inputs = False
        import inspect

        from cascade.spec.dsl.resources import Inject

        def check_complexity(obj):
            if isinstance(obj, Inject):
                return True
            if isinstance(obj, (list, tuple)):
                return any(check_complexity(x) for x in obj)
            if isinstance(obj, dict):
                return any(check_complexity(x) for x in obj.values())
            return False

        # Create a unified view of all inputs
        all_inputs = {str(i): v for i, v in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for k, v in all_inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue

            # If it's a direct dependency string, don't add to bindings
            if self._is_dependency(v):
                continue

            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True

        # Also check the executable signature for Inject defaults
        if not has_complex_inputs:
            executable = executables.get(node_ir.current_node_instance_hash)
            if executable:
                try:
                    sig = inspect.signature(executable)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            has_complex_inputs = True
                            break
                except (ValueError, TypeError):
                    pass

        # Determine Node Type
        if node_ir.type == "map":
            node = MapNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="map",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
            )
        elif node_ir.type == "param":
            node = ParamNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="param",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=True,
            )
        else:
            node = TaskNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="task",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex_inputs,
            )

        return node

    def _create_edges(self, node_ir: NodeIR, target_node: Node):
        # Create a unified view of all inputs
        all_inputs = {str(i): v for i, v in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        # 1. Data Edges & Routers
        for arg_name, value in all_inputs.items():
            if self._is_dependency(value):
                # Simple Data Dependency (Node ID ref)
                source_node = self.node_map[value]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name=arg_name,
                        edge_type=EdgeType.DATA,
                    )
                )
            elif isinstance(value, dict) and value.get("$router"):
                # Reconstruct Router
                self._reconstruct_router_edges(value, arg_name, target_node)
            else:
                # Recursively scan for nested dependencies to ensure Graph connectivity
                self._scan_and_create_nested_edges(value, arg_name, target_node)

        # 2. Condition
        if node_ir.condition and node_ir.condition in self.node_map:
            source_node = self.node_map[node_ir.condition]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )

        # 3. Sequencing Dependencies
        for dep_id in node_ir.dependencies:
            if dep_id in self.node_map:
                source_node = self.node_map[dep_id]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name="<sequence>",
                        edge_type=EdgeType.SEQUENCE,
                    )
                )

        # 4. Jump / Flow Control
        if node_ir.flow_control:
            self._reconstruct_jump_edges(node_ir.flow_control, target_node)

        # 5. Constraint Edges
        if node_ir.constraints:
            from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

            for key, val in node_ir.constraints.items():
                if (
                    isinstance(val, (LazyResult, MappedLazyResult))
                    and val._uuid in self.logical_map
                ):
                    source_node = self.logical_map[val._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=source_node,
                            target=target_node,
                            arg_name=key,
                            edge_type=EdgeType.CONSTRAINT,
                        )
                    )

    def _scan_and_create_nested_edges(self, obj: Any, arg_name: str, target_node: Node):
        if self._is_dependency(obj):
            source_node = self.node_map[obj]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name=arg_name,
                    edge_type=EdgeType.DATA,
                )
            )
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._scan_and_create_nested_edges(item, arg_name, target_node)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._scan_and_create_nested_edges(value, arg_name, target_node)

    def _reconstruct_router_edges(
        self, router_def: dict[str, Any], arg_name: str, target_node: Node
    ):
        selector_id = router_def["selector"]
        routes_def = router_def["routes"]

        if selector_id not in self.node_map:
            return  # Error or stub?

        selector_node = self.node_map[selector_id]

        selector_stub = _StubLazyResult(selector_id)
        routes_stubs = {k: _StubLazyResult(v) for k, v in routes_def.items() if v}

        router_obj = Router(selector=selector_stub, routes=routes_stubs)  # type: ignore

        # 1. Edge from Selector -> Target (carrying Router obj)
        self.graph.add_edge(
            Edge(
                source=selector_node,
                target=target_node,
                arg_name=arg_name,
                edge_type=EdgeType.DATA,
                router=router_obj,
            )
        )

        # 2. Edges from Routes -> Target
        for key, route_node_id in routes_def.items():
            if route_node_id and route_node_id in self.node_map:
                route_node = self.node_map[route_node_id]
                self.graph.add_edge(
                    Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"{arg_name}.route[{key}]",
                        edge_type=EdgeType.ROUTER_ROUTE,
                    )
                )

    def _reconstruct_jump_edges(self, flow_control: dict[str, Any], source_node: Node):
        routes_stubs = {
            k: (_StubLazyResult(v) if v else None) for k, v in flow_control.items()
        }
        selector_obj = JumpSelector(routes=routes_stubs)  # type: ignore

        # Add edges for each potential jump target
        for key, target_logical_id in flow_control.items():
            if target_logical_id and target_logical_id in self.logical_map:
                target_node = self.logical_map[target_logical_id]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name=key,
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector_obj,
                    )
                )
