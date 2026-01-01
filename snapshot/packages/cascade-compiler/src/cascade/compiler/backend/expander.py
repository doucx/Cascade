from dataclasses import dataclass, field
from typing import List, Dict

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
    """
    A collection of physical nodes and channels that represent a single logical unit
    (e.g., a Triad).
    """
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)
    
    # Interface pointers
    bleacher: BleachNode = None
    stainer: StainNode = None


class Expander:
    """
    The 'Big Bang' engine. 
    It expands a single logical NodeIR into a physical Triad SubGraph.
    
    Triad Structure:
        F_pre (Bleacher) --> D_worker_in --> F_worker --> D_worker_out --> F_post (Stainer)
               |                                                              ^
               +---------------------> D_trace -------------------------------+
    """
    
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        """
        Expands a NodeIR into a physical Triad.
        """
        subgraph = SubGraph()
        
        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.id
        
        f_pre_id = f"{base_id}_bleach"
        d_worker_in_id = f"{base_id}_worker_in"
        f_worker_id = f"{base_id}_worker"
        d_worker_out_id = f"{base_id}_worker_out"
        d_trace_id = f"{base_id}_trace"
        f_post_id = f"{base_id}_stain"
        
        # 2. Create Nodes
        
        # F_pre: The Bleacher
        # It needs input ports matching the Task definition args.
        bleacher_inputs = {arg.name: "Any" for arg in node_ir.task.args}
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": "Dict", 
                "trace_output": "TraceCtx"
            }
        )
        
        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(
            id=d_worker_in_id,
            name=f"In({node_ir.name})"
        )
        
        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={"worker_input": "Dict"},
            output_ports={"worker_result": "Any"}
        )
        
        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(
            id=d_worker_out_id,
            name=f"Out({node_ir.name})"
        )
        
        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(
            id=d_trace_id,
            name=f"Trace({node_ir.name})"
        )
        
        # F_post: The Stainer
        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": "Any",
                "trace_input": "TraceCtx"
            },
            output_ports={
                "output": "Token"
            }
        )
        
        # Register nodes
        subgraph.nodes = {
            n.id: n for n in [
                f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post
            ]
        }
        subgraph.bleacher = f_pre
        subgraph.stainer = f_post
        
        # 3. Create Internal Wiring (Channels)
        
        channels = []
        
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(Channel(f_pre_id, "worker_input", d_worker_in_id))
        # D_worker_in -> F_worker
        channels.append(Channel(d_worker_in_id, "out", f_worker_id)) # Implicit 'out' for DataNode source
        # F_worker -> D_worker_out
        channels.append(Channel(f_worker_id, "worker_result", d_worker_out_id))
        # D_worker_out -> F_post
        channels.append(Channel(d_worker_out_id, "out", f_post_id))
        
        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(Channel(f_pre_id, "trace_output", d_trace_id))
        # D_trace -> F_post
        channels.append(Channel(d_trace_id, "out", f_post_id))
        
        subgraph.channels = channels
        
        return subgraph