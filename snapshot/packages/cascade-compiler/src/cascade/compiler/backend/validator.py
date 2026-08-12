from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.topology import BipartiteGraph


class GraphValidationError(ValueError):
    pass


class GraphValidator:
    def validate(self, graph: BipartiteGraph, graph_ir: GraphIR) -> None:
        self._check_node_integrity(graph)
        self._check_bipartite_rule(graph)
        self._check_port_connectivity(graph)

    def _check_node_integrity(self, graph: BipartiteGraph) -> None:
        for i, channel in enumerate(graph.channels):
            if channel.source_node_id not in graph.nodes:
                raise GraphValidationError(
                    f"Channel #{i} references missing source node '{channel.source_node_id}'"
                )
            if channel.target_node_id not in graph.nodes:
                raise GraphValidationError(
                    f"Channel #{i} references missing target node '{channel.target_node_id}'"
                )

    def _check_bipartite_rule(self, graph: BipartiteGraph) -> None:
        for i, channel in enumerate(graph.channels):
            src = graph.nodes[channel.source_node_id]
            tgt = graph.nodes[channel.target_node_id]

            src_is_data = isinstance(src, PhysicsDataNode)
            tgt_is_data = isinstance(tgt, PhysicsDataNode)

            if src_is_data == tgt_is_data:
                node_type = "DataNode" if src_is_data else "FuncNode"
                raise GraphValidationError(
                    f"Bipartite rule violated in Channel #{i}: "
                    f"{node_type}('{src.id}') -> {node_type}('{tgt.id}'). "
                    "Connections must be between distinct node types."
                )

    def _check_port_connectivity(self, graph: BipartiteGraph) -> None:
        for i, channel in enumerate(graph.channels):
            src = graph.nodes[channel.source_node_id]
            tgt = graph.nodes[channel.target_node_id]

            # 1. Check Source Port
            if isinstance(src, PhysicsFuncNode):
                if channel.source_port not in src.output_ports:
                    raise GraphValidationError(
                        f"Channel #{i}: Output port '{channel.source_port}' not found "
                        f"on FuncNode '{src.id}'. Available: {list(src.output_ports.keys())}"
                    )
            elif isinstance(src, PhysicsDataNode):
                # DataNodes typically have a generic 'out' behavior,
                # but we can enforce 'out' convention if strictness is desired.
                # For now, we assume any output from DataNode is valid (it's just taking a token).
                pass

            # 2. Check Target Port
            if isinstance(tgt, PhysicsFuncNode):
                if channel.target_port not in tgt.input_ports:
                    raise GraphValidationError(
                        f"Channel #{i}: Input port '{channel.target_port}' not found "
                        f"on FuncNode '{tgt.id}'. Available: {list(tgt.input_ports.keys())}"
                    )
            elif isinstance(tgt, PhysicsDataNode):
                # DataNodes typically receive on 'in'.
                if channel.target_port != "in":
                    raise GraphValidationError(
                        f"Channel #{i}: DataNode '{tgt.id}' expects input on port 'in', "
                        f"got '{channel.target_port}'."
                    )
