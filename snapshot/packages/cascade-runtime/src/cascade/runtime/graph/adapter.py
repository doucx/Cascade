from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass

from cascade.spec.ir.graph import GraphIR, NodeIR
from cascade.compiler.frontend.generator import GenerationResult
from cascade.graph.model import (
    Graph,
    Node,
    TaskNode,
    MapNode,
    ParamNode,
    Edge,
    EdgeType,
)
from cascade.graph.registry import NodeRegistry
from cascade.spec.dsl.fluent import RetryPolicy
from cascade.spec.dsl.constraint import ResourceConstraint
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.jump import JumpSelector


@dataclass
class _StubLazyResult:
    """A minimal stub to satisfy runtime checks for UUID presence."""
    _uuid: str


class IRToRuntimeAdapter:
    def __init__(self, registry: Optional[NodeRegistry] = None):
        self.registry = registry or NodeRegistry()
        self.graph = Graph()
        # Maps node_instance_hash -> Runtime Node Object
        self.node_map: Dict[str, Node] = {}
        # Maps logical_uuid (from IR) -> Runtime Node Object (for router reconstruction)
        self.logical_map: Dict[str, Node] = {}

    def adapt(
        self, result: GenerationResult
    ) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
        ir = result.ir
        executables = result.executables

        # 1. Create Nodes
        for node_ir in ir.nodes:
            node = self._create_node(node_ir)
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
        instance_map: Dict[str, Node] = {}
        for node_ir in ir.nodes:
            if node_ir.logical_id:
                instance_map[node_ir.logical_id] = self.node_map[
                    node_ir.current_node_instance_hash
                ]

        return self.graph, instance_map, executables

    def _create_node(self, node_ir: NodeIR) -> Node:
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
            # Note: Dynamic constraints (LazyResults) are stored as UUID strings in IR constraints dict
            # if they were properly processed. But IRGenerator currently copies requirements dict.
            # If IRGenerator leaves LazyResult objects in constraints, we might have issues if strict JSON is needed.
            # For now, assuming in-memory transfer, objects might be fine, but spec says IR should be simple.
            # The current IRGenerator implementation copies the dict.
            # We wrap it back into ResourceConstraint.
            constraints = ResourceConstraint(requirements=node_ir.constraints)

        # Input bindings: filter out router definitions from inputs
        input_bindings = {}
        for k, v in node_ir.inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue
            input_bindings[k] = v

        # Determine Node Type
        if node_ir.type == "map":
            node = MapNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="map",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
            )
        elif node_ir.type == "param":
            node = ParamNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="param",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=True,
            )
        else:
            # Check for complex inputs (heuristic)
            # In new IR, we might want an explicit flag. For now, assume False unless proven otherwise?
            # Or safe default True? GraphBuilder logic was complex.
            # Let's assume False for standard tasks unless we see specialized inputs.
            # Actually, Runtime ArgumentResolver handles complex inputs fine even if flag is False,
            # it just skips the "Fast Path". Setting False is safe but maybe slower.
            # Setting True forces complex path.
            # Let's check bindings for nested structures.
            node = TaskNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="task",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=False,  # TODO: Optimization: detect complexity
            )

        return node

    def _create_edges(self, node_ir: NodeIR, target_node: Node):
        # 1. Data Edges & Routers
        for arg_name, value in node_ir.inputs.items():
            if isinstance(value, str) and value in self.node_map:
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

    def _reconstruct_router_edges(
        self, router_def: Dict[str, Any], arg_name: str, target_node: Node
    ):
        selector_id = router_def["selector"]
        routes_def = router_def["routes"]

        if selector_id not in self.node_map:
            return  # Error or stub?

        selector_node = self.node_map[selector_id]

        # Reconstruct Router Object with Stubs
        # The runtime needs selector._uuid and route_val._uuid
        # We need to find the logical IDs for these physical nodes to populate the stubs correctly?
        # GraphIR stores physical IDs in 'selector' and 'routes'.
        # But LazyResult._uuid usually matches logical_id.
        # Wait, IRGenerator resolves everything to Physical IDs (Node Instance Hashes).
        # But _StubLazyResult needs a UUID that matches keys in instance_map.
        # FlowManager uses: `instance_map[instance._uuid]`
        # So we must put the LOGICAL UUID into the stub if we want FlowManager to find the node in instance_map.

        # Problem: NodeIR inputs store PHYSICAL IDs (hashes).
        # We need a reverse map from Physical ID -> Logical ID to populate the stub correctly?
        # Or, we update instance_map to ALSO support Physical IDs?
        # -> Updating instance_map to support Physical IDs is robust and easier.
        # BUT, FlowManager logic is: `self.instance_map.get(instance._uuid)`
        # So if we put physical ID in stub._uuid, and ensure instance_map has physical keys, it works.

        selector_stub = _StubLazyResult(selector_id)
        routes_stubs = {
            k: _StubLazyResult(v) for k, v in routes_def.items() if v
        }

        router_obj = Router(selector=selector_stub, routes=routes_stubs) # type: ignore

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

    def _reconstruct_jump_edges(
        self, flow_control: Dict[str, Any], source_node: Node
    ):
        # Flow control in IR: {"target_key": "target_node_id"}
        # Runtime expects EdgeType.ITERATIVE_JUMP from Source -> Target
        # carrying a JumpSelector object.

        routes_stubs = {
            k: (_StubLazyResult(v) if v else None) for k, v in flow_control.items()
        }
        selector_obj = JumpSelector(routes=routes_stubs) # type: ignore

        # Add edges for each potential jump target
        for key, target_id in flow_control.items():
            if target_id and target_id in self.node_map:
                target_node = self.node_map[target_id]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name=key,
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector_obj,
                    )
                )