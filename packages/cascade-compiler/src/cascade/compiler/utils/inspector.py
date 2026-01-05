from typing import Optional, List
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsNode, PhysicsFuncNode, PhysicsDataNode
from cascade.spec.physical.ports import PortRole


class InspectionError(AssertionError):
    pass


class GraphInspector:
    def __init__(self, graph: BipartiteGraph):
        self.graph = graph

    def get_node(self, node_id: str) -> PhysicsNode:
        if node_id not in self.graph.nodes:
            raise InspectionError(f"Node '{node_id}' not found in graph.")
        return self.graph.nodes[node_id]

    def get_func_node(self, node_id: str) -> PhysicsFuncNode:
        node = self.get_node(node_id)
        if not isinstance(node, PhysicsFuncNode):
            raise InspectionError(f"Node '{node_id}' is not a FuncNode.")
        return node

    def get_data_node(self, node_id: str) -> PhysicsDataNode:
        node = self.get_node(node_id)
        if not isinstance(node, PhysicsDataNode):
            raise InspectionError(f"Node '{node_id}' is not a DataNode.")
        return node

    def assert_node_exists(self, node_id: str) -> None:
        self.get_node(node_id)

    def assert_port_exists(
        self, node_id: str, port_name: str, direction: str = "output"
    ) -> None:
        node = self.get_func_node(node_id)
        ports = node.input_ports if direction == "input" else node.output_ports
        if port_name not in ports:
            raise InspectionError(
                f"FuncNode '{node_id}' does not have {direction} port '{port_name}'. "
                f"Available: {list(ports.keys())}"
            )

    def assert_port_count(
        self,
        node_id: str,
        count: int,
        direction: str = "output",
        role: Optional[PortRole] = None,
    ) -> None:
        node = self.get_func_node(node_id)
        ports = node.input_ports if direction == "input" else node.output_ports

        filtered_ports = ports
        if role:
            filtered_ports = {name: p for name, p in ports.items() if p.role == role}

        if len(filtered_ports) != count:
            raise InspectionError(
                f"FuncNode '{node_id}' expected {count} {direction} ports"
                + (f" with role {role}" if role else "")
                + f", but found {len(filtered_ports)}."
            )

    def assert_connection(
        self,
        source_id: str,
        target_id: str,
        source_port: Optional[str] = None,
        target_port: Optional[str] = None,
    ) -> Channel:
        candidates = [
            c
            for c in self.graph.channels
            if c.source_node_id == source_id and c.target_node_id == target_id
        ]

        if not candidates:
            raise InspectionError(
                f"No channel found from '{source_id}' to '{target_id}'."
            )

        # Filter by ports if provided
        matches = candidates
        if source_port:
            matches = [c for c in matches if c.source_port == source_port]
            if not matches:
                raise InspectionError(
                    f"No channel from '{source_id}' port '{source_port}' to '{target_id}'."
                )

        if target_port:
            matches = [c for c in matches if c.target_port == target_port]
            if not matches:
                raise InspectionError(
                    f"No channel from '{source_id}' to '{target_id}' port '{target_port}'."
                )

        return matches[0]

    def find_channels_from(
        self, source_id: str, source_port: Optional[str] = None
    ) -> List[Channel]:
        return [
            c
            for c in self.graph.channels
            if c.source_node_id == source_id
            and (source_port is None or c.source_port == source_port)
        ]
