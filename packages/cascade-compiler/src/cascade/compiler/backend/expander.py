from dataclasses import dataclass, field
from typing import List, Dict

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: BleachNode = None
    stainer: StainNode = None


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
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
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {arg.name: "Any" for arg in node_ir.task.args}
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            bleacher_inputs[f"res_{res_name}"] = "ResourceSlot"

        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": "Dict",
                "trace_output": "TraceCtx",
                "obs_output": "Event",  # Port for start event
            },
        )

        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(id=d_worker_in_id, name=f"In({node_ir.name})")

        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={"worker_input": "Dict"},
            output_ports={"worker_result": "Any"},
        )

        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(id=d_worker_out_id, name=f"Out({node_ir.name})")

        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        stainer_outputs = {
            "output": "Token",
            "obs_output": "Event",
        }
        for res_name in node_ir.constraints.keys():
            stainer_outputs[f"res_{res_name}"] = "ResourceSlot"

        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={"worker_result": "Any", "trace_input": "TraceCtx"},
            output_ports=stainer_outputs,
        )

        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
        subgraph.stainer = f_post

        # 3. Create Internal Wiring (Channels)

        channels = []

        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="worker_input",
                target_node_id=d_worker_in_id,
                target_port="in",
            )
        )
        # D_worker_in -> F_worker
        channels.append(
            Channel(
                source_node_id=d_worker_in_id,
                source_port="out",
                target_node_id=f_worker_id,
                target_port="worker_input",
            )
        )
        # F_worker -> D_worker_out
        channels.append(
            Channel(
                source_node_id=f_worker_id,
                source_port="worker_result",
                target_node_id=d_worker_out_id,
                target_port="in",
            )
        )
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="trace_output",
                target_node_id=d_trace_id,
                target_port="in",
            )
        )
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )

        subgraph.channels = channels

        return subgraph
