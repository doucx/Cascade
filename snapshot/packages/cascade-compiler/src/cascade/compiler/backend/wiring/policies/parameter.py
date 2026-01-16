from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.specs.dyad import LanderSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
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
