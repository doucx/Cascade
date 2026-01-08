from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy
from cascade.spec.physical.constants import NodePrefix


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 4.2 Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"

                # Violation Fix: Insert D_seq
                d_seq_id = f"seq.{dep_id}.to.{node_ir.current_node_instance_hash}"
                d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                ctx.wire.add_node(d_seq)

                ctx.wire.connect(
                    source_subgraph.stainer.id, "output_default", d_seq_id, "in"
                )
                ctx.wire.connect(d_seq_id, "out", subgraph.bleacher.id, port_name)

        # 4.3 Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            # Violation Fix: Insert D_cond
            d_cond_id = (
                f"cond.{node_ir.condition}.to.{node_ir.current_node_instance_hash}"
            )
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)

            ctx.wire.connect(
                source_subgraph.stainer.id, "output_default", d_cond_id, "in"
            )
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")

        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, "output_default", d_egress_id, "in")
