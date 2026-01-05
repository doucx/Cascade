from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.reflection import PhysicalIdGenerator


@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        subgraph = SubGraph()

        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.current_node_instance_hash

        f_pre_id = PhysicalIdGenerator.bleach_node(base_id)
        d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
        f_worker_id = PhysicalIdGenerator.worker_node(base_id)
        d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
        d_trace_id = PhysicalIdGenerator.trace_data(base_id)
        f_post_id = PhysicalIdGenerator.stain_node(base_id)

        # 2. Create Nodes

        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        # Add ports for implicit dependencies (SIGNAL)
        for dep_id in node_ir.dependencies:
            # We use a naming convention for dependency ports
            port_name = f"wait_for_{dep_id}"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Token")

        # Add port for condition (SIGNAL/DATA)
        if node_ir.condition:
            port_name = "condition"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        # If after all that, there are no inputs, it's a source node that needs a pulse.
        if not bleacher_inputs:
            bleacher_inputs[PortName.PULSE] = PortDef(PortName.PULSE, PortRole.SIGNAL)

        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict"),
                "trace_output": PortDef("trace_output", PortRole.DATA, "TraceCtx"),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
            },
        )

        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(id=d_worker_in_id, name=f"In({node_ir.name})")

        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict")
            },
            output_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any")
            },
        )

        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(id=d_worker_out_id, name=f"Out({node_ir.name})")

        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        # Sovereign Ports: Explicitly define default and error paths
        stainer_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            stainer_outputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any"),
                "trace_input": PortDef("trace_input", PortRole.DATA, "TraceCtx"),
            },
            output_ports=stainer_outputs,
        )

        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
        subgraph.worker = f_worker
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
