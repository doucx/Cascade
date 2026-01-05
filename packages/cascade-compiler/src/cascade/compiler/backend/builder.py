from typing import List

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from cascade.spec.assembly import Assembly
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy
from cascade.compiler.wiring.policies.parameter import ParameterWiringPolicy
from cascade.compiler.wiring.policies.control import ControlFlowWiringPolicy
from cascade.compiler.wiring.policies.observability import ObservabilityWiringPolicy
from cascade.compiler.wiring.policies.resource import ResourceWiringPolicy
from cascade.compiler.wiring.policies.pulse import PulseWiringPolicy


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()
        self._policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> Assembly:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )
        symbol_table = {}

        # 2. Phase 0: Setup Global Infrastructure
        for policy in self._policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Expand and Wire Nodes
        for node_ir in graph_ir.nodes:
            # 3.1 Expand triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.current_node_instance_hash, subgraph)

            # 3.1.b Populate Symbol Table
            # Map the physical worker ID to the canonical code structure hash
            if subgraph.worker:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.worker.id] = canonical_hash

            # 3.2 Apply wiring policies
            for policy in self._policies:
                policy.apply(ctx, node_ir, subgraph)

        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        return Assembly(
            graph=physical_graph,
            symbol_table=symbol_table,
            metadata={"compiler": "cascade-compiler-v0.1.0"},
        )
