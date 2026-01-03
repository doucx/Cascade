from typing import Dict

from cascade.spec.ir.models import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy
from cascade.compiler.wiring.prism import ResourcePrism
from cascade.compiler.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
    def __init__(self):
        self._prisms: Dict[str, ResourcePrism] = {
            "discrete": DiscreteResourcePrism(),
        }

    def setup_globals(self, ctx: WiringContext) -> None:
        # Create Global Brokers for each resource based on its type
        for res_def in ctx.environment.resources:
            prism = self._get_prism(res_def.type)
            prism.ensure_globals(ctx, res_def)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        # Validate and Wire constraints
        env_resources = {r.name: r for r in ctx.environment.resources}
        for res_name in node_ir.constraints:
            if res_name not in env_resources:
                raise ValueError(
                    f"Resource '{res_name}' required by node '{node_ir.id}' is not defined"
                )

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.connect_task(ctx, node_ir, subgraph, res_name, amount)

    def _get_prism(self, type_name: str) -> ResourcePrism:
        if type_name not in self._prisms:
            raise ValueError(f"Unknown resource type: '{type_name}'")
        return self._prisms[type_name]
