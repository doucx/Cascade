from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.ports import PortName
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class PulseWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # Identify Source Nodes
        # A true source has no inputs, dependencies, conditions, or constraints.
        is_true_source = (
            not node_ir.inputs
            and not node_ir.dependencies
            and not node_ir.condition
            and not node_ir.constraints
        )

        if is_true_source:
            d_pulse_id = PhysicalIdGenerator.pulse_source(
                node_ir.current_node_instance_hash
            )
            d_pulse = PhysicsDataNode(
                id=d_pulse_id,
                name=f"Pulse({node_ir.current_node_instance_hash})",
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            ctx.wire.connect(d_pulse_id, "out", subgraph.bleacher.id, PortName.PULSE)
