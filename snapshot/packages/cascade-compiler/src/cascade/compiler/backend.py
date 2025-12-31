import hashlib
from typing import List, Dict, Any

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
        self._initial_values = {}
        
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        # Also process literal inputs in this pass
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on Edges (Dependencies)
        # This will OVERWRITE any literal inputs if an edge exists for the same arg
        # (Though IR shouldn't have both literal and edge for same arg)
        self._process_edges()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

    def _process_node(self, node_ir):
        func_hash = node_ir.current_node_instance_hash
        
        # 1. Create PhysicsFuncNode
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node

        # 1.5 Process Literals (args/kwargs)
        # Convert args to position-based names ("0", "1", ...)
        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)
        
        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        # 2. Create Default Output DataNode (Slot)
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
            tag_filter="default" 
        )
        self._channels.append(channel)

    def _process_literal(self, f_node, arg_name, value):
        # Create a Constant DataNode for this value
        # Hash based on value repr to allow deduplication of same constants
        const_hash = self._compute_const_hash(value)
        
        if const_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=const_hash,
                name=f"const_{const_hash[:8]}",
                producer_node_instance_hash="const"
            )
            self._data_nodes[const_hash] = d_node
            self._initial_values[const_hash] = value
            
        # Wire it up
        f_node.inputs[arg_name] = const_hash

    def _process_edges(self):
        for edge in self._graph.edges:
            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _compute_const_hash(self, value: Any) -> str:
        # Simple content hashing for literals
        # Warning: repr() isn't stable for all types, but good enough for primitives
        # In production, use a better serializer
        raw = f"const:{repr(value)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()