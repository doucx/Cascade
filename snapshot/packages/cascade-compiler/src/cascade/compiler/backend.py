import hashlib
from typing import List, Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
)


class Backend:
    """
    Compiler Backend: Transforms GraphIR into a static BipartiteGraph topology.
    """

    @staticmethod
    def compile(graph: GraphIR) -> BipartiteGraph:
        builder = _TopologyBuilder(graph)
        return builder.build()


class _TopologyBuilder:
    def __init__(self, graph: GraphIR):
        self._graph = graph
        self._func_nodes: Dict[str, PhysicsFuncNode] = {}
        self._data_nodes: Dict[str, PhysicsDataNode] = {}
        self._channels: List[ChannelDef] = []
        
        # Helper map: FuncNode Hash -> Default Output DataNode Hash
        self._func_output_map: Dict[str, str] = {}

    def build(self) -> BipartiteGraph:
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on Edges
        self._process_edges()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
        )

    def _process_node(self, node_ir):
        func_hash = node_ir.current_node_instance_hash
        
        # 1. Create PhysicsFuncNode
        # Inputs will be populated in Pass 2
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node

        # 2. Create Default Output DataNode (Slot)
        # We assume a single output port named "result" for now.
        # The data slot hash is deterministically derived from the producer + port.
        data_slot_hash = self._compute_data_slot_hash(func_hash, "result")
        self._func_output_map[func_hash] = data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=func_hash
        )
        self._data_nodes[data_slot_hash] = d_node

        # 3. Create Output Channel (Func -> Data)
        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default" # Default filter
        )
        self._channels.append(channel)

    def _process_edges(self):
        for edge in self._graph.edges:
            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            # In IR, edges are direct Func->Func. 
            # In Topology, we must route through the DataNode.
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                # Should not happen in valid IR
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                # Note: PhysicsFuncNode is frozen, but we are in construction phase.
                # Since dataclasses are frozen=True, we technically cannot mutate 'inputs'.
                # However, 'inputs' is a mutable dict (default_factory), so we CAN mutate its content
                # unless we made it immutable/frozen too. Standard dataclass behavior allows 
                # mutating the mutable content of a frozen field.
                target_func_node.inputs[arg_name] = source_data_hash

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()