import sys
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.spec.components import ObservabilitySpec, BleacherSpec, StainerSpec
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ObservabilityWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )

        # Use Spec to define ports
        spec = ObservabilitySpec
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                spec.event_token.name: PortDef(
                    spec.event_token.name, PortRole.OBSERVABILITY, "Event"
                )
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        ctx.wire.add_node(d_life)
        ctx.wire.add_node(f_obs)

        ctx.wire.connect(d_life_id, "out", f_obs_id, spec.event_token.name)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None
        assert subgraph.stainer is not None

        d_life_id = PhysicalIdGenerator.observability_bus()

        # Wire task observability TO the sidecar bus
        ctx.wire.connect(
            subgraph.bleacher.id, BleacherSpec.obs_output.name, d_life_id, "in"
        )
        ctx.wire.connect(
            subgraph.stainer.id, StainerSpec.obs_output.name, d_life_id, "in"
        )
