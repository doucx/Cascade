from cascade.spec.compiler.interfaces import WiringPolicy
from cascade.spec.components import EgressSpec
from cascade.spec.ir.graph import NodeIR
from cascade.spec.specs.dyad import LanderSpec, LauncherSpec

from ...expander import SubGraph
from ..context import WiringContext


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.lander is not None

                port_name = f"wait_for_{dep_id}"
                d_seq = subgraph.controls[f"seq_from_{dep_id}"]

                # Source Lander -> D_seq -> Target Launcher
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_seq.id,
                    "in",
                )
                ctx.wire.connect(d_seq.id, "out", subgraph.launcher.id, port_name)

        # 2. Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.lander is not None

            d_cond = subgraph.controls[f"cond_from_{node_ir.condition}"]

            # Source Lander -> D_cond -> Target Launcher
            ctx.wire.connect(
                source_subgraph.lander.id,
                LanderSpec.output_default.name,
                d_cond.id,
                "in",
            )
            ctx.wire.connect(
                d_cond.id, "out", subgraph.launcher.id, LauncherSpec.condition.name
            )

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.lander is not None
            d_egress = subgraph.controls[f"egress_for_{node_ir.logical_id}"]

            # Lander -> D_egress (which goes to F_egress)
            ctx.wire.connect(
                subgraph.lander.id,
                LanderSpec.output_default.name,
                d_egress.id,
                EgressSpec.input_token.name,
            )
