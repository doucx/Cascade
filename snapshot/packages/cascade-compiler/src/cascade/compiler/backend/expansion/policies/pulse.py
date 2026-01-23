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
        # Determine if the node needs a self-bootstrapping pulse.
        # It needs a pulse if it has NO upstream execution dependencies.

        # 1. Check Explicit Sequence Dependencies (.after())
        has_dependencies = len(node_ir.dependencies) > 0

        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        all_input_values = list(node_ir.args) + list(node_ir.kwargs.values())
        for value in all_input_values:
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break

        # 3. Check Condition (.run_if())
        has_condition = node_ir.condition is not None

        # Decision: If there are no upstream triggers, we must provide a pulse.
        # Note: Static inputs (constants) and Resource Constraints do not count as
        # execution dependencies; they are pre-requisites but not triggers.
        needs_pulse = not (has_dependencies or has_data_dependency or has_condition)

        if needs_pulse:
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
