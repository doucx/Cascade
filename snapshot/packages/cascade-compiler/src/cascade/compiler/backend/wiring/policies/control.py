from cascade.spec.ir.graph import NodeIR
from cascade.spec.components import StainerSpec, BleacherSpec, EgressSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"
                d_seq = subgraph.controls[f"seq_from_{dep_id}"]

                ctx.wire.connect(
                    source_subgraph.stainer.id,
                    StainerSpec.output_default.name,
                    d_seq.id,
                    "in",
                )
                ctx.wire.connect(d_seq.id, "out", subgraph.bleacher.id, port_name)

        # 2. Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            d_cond = subgraph.controls[f"cond_from_{node_ir.condition}"]

            ctx.wire.connect(
                source_subgraph.stainer.id,
                StainerSpec.output_default.name,
                d_cond.id,
                "in",
            )
            ctx.wire.connect(
                d_cond.id, "out", subgraph.bleacher.id, BleacherSpec.condition.name
            )

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            d_egress = subgraph.controls[f"egress_for_{node_ir.logical_id}"]

            ctx.wire.connect(
                subgraph.stainer.id,
                StainerSpec.output_default.name,
                d_egress.id,
                EgressSpec.input_token.name,
            )
