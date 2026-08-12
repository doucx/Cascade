import sys

from cascade.reflection import PhysicalIdGenerator
from cascade.spec.compiler.interfaces import WiringPolicy
from cascade.spec.components import ObservabilitySpec
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.system_nodes import ObservabilityNode
from cascade.spec.specs.dyad import LanderSpec, LauncherSpec

from ...expander import SubGraph
from ..context import WiringContext


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
        assert subgraph.launcher is not None
        assert subgraph.lander is not None

        d_life_id = PhysicalIdGenerator.observability_bus()

        # Wire Launcher observability (STARTED event)
        ctx.wire.connect(
            subgraph.launcher.id, LauncherSpec.obs_output.name, d_life_id, "in"
        )

        # Wire Lander observability (FINISHED event)
        ctx.wire.connect(
            subgraph.lander.id, LanderSpec.obs_output.name, d_life_id, "in"
        )
