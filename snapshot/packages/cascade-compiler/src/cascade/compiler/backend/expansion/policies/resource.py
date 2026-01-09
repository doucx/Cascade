from typing import Dict, cast

from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.wiring.prism import ResourcePrism
from cascade.compiler.backend.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
    def __init__(self):
        # In a more advanced system, this could be a dynamic registry.
        # For now, we hardcode the known prism implementations.
        self._prisms: Dict[str, ResourcePrism] = {
            "discrete": DiscreteResourcePrism(),
        }

    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        env_resources = {r.name: r for r in ctx.environment.resources}

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.expand_task(ctx, node_ir, subgraph, res_name, amount)

    def _get_prism(self, type_name: str) -> ResourcePrism:
        if type_name not in self._prisms:
            raise ValueError(f"Unknown resource type: '{type_name}'")
        return self._prisms[type_name]