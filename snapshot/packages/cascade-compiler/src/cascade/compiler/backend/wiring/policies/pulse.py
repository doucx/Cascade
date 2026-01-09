from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import BleacherSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class PulseWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # Check if a pulse source was created for this node during expansion
        if "pulse_source" in subgraph.controls:
            d_pulse = subgraph.controls["pulse_source"]
            ctx.wire.connect(
                d_pulse.id, "out", subgraph.bleacher.id, BleacherSpec.pulse.name
            )