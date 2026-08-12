from cascade.spec.compiler.interfaces import WiringPolicy
from cascade.spec.ir.graph import NodeIR
from cascade.spec.specs.dyad import LanderSpec

from ...expander import SubGraph
from ..context import WiringContext


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # The physical port name MUST be the input key itself (either digit for args or string for kwargs)
            # to ensure a direct mapping from IR to the physical graph.
            port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.lander is not None

                # Retrieve the intermediate node created during expansion
                d_dep = subgraph.controls[f"dep_for_{input_key}"]

                # Connect: Source Lander -> D_dep
                # Note: LanderSpec uses 'output_default' just like StainerSpec did
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_dep.id,
                    "in",
                )

                # Connect: D_dep -> Target Launcher
                ctx.wire.connect(d_dep.id, "out", subgraph.launcher.id, port_name)

            # Case B: Literal Value (Constant)
            else:
                # Retrieve the constant node created during expansion
                d_const = subgraph.constants[input_key]

                # Connect: D_const -> Launcher
                ctx.wire.connect(d_const.id, "out", subgraph.launcher.id, port_name)
