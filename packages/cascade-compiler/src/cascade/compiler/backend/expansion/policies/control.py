from cascade.spec.compiler.interfaces import ExpansionPolicy
from cascade.spec.components import EgressSpec
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.constants import NodePrefix
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole

from ...expander import SubGraph
from ..context import ExpansionContext


class ControlFlowExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            d_seq_id = f"seq.{dep_id}.to.{node_ir.current_node_instance_hash}"
            d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
            ctx.wire.add_node(d_seq)
            subgraph.nodes[d_seq.id] = d_seq
            subgraph.controls[f"seq_from_{dep_id}"] = d_seq

        # 2. Condition (.run_if())
        if node_ir.condition:
            d_cond_id = (
                f"cond.{node_ir.condition}.to.{node_ir.current_node_instance_hash}"
            )
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)
            subgraph.nodes[d_cond.id] = d_cond
            subgraph.controls[f"cond_from_{node_ir.condition}"] = d_cond

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            # 3.1 D_buffer (The waiting room)
            d_buffer_id = f"buffer.egress.{node_ir.logical_id}"
            d_buffer = PhysicsDataNode(
                id=d_buffer_id, name=f"BufEgress({node_ir.name})"
            )
            ctx.wire.add_node(d_buffer)
            subgraph.nodes[d_buffer.id] = d_buffer

            # 3.2 F_egress (The active exporter)
            f_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            f_egress = PhysicsFuncNode(
                id=f_egress_id,
                name=f"Egress({node_ir.name})",
                input_ports={
                    EgressSpec.input_token.name: PortDef(
                        EgressSpec.input_token.name, PortRole.DATA
                    )
                },
            )
            ctx.wire.add_node(f_egress)
            subgraph.nodes[f_egress.id] = f_egress

            # 3.3 Wire Buffer -> F_egress
            ctx.wire.connect(
                d_buffer_id, "out", f_egress_id, EgressSpec.input_token.name
            )

            # 3.4 Expose Buffer for Wiring (Stainer -> Buffer)
            # The Wiring Policy connects the Stainer output to this node.
            subgraph.controls[f"egress_for_{node_ir.logical_id}"] = d_buffer
