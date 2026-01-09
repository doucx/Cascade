from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.constants import NodePrefix
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy


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
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)
            subgraph.nodes[d_egress.id] = d_egress
            subgraph.controls[f"egress_for_{node_ir.logical_id}"] = d_egress
