from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.reflection import PhysicalIdGenerator
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy


class PulseExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
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
            subgraph.nodes[d_pulse.id] = d_pulse
            subgraph.controls["pulse_source"] = d_pulse
