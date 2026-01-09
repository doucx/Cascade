from typing import List

from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.assembly import (
    Assembly,
    CompilationArtifact,
    CompilationManifest,
)
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.wiring.policies.parameter import ParameterWiringPolicy
from cascade.compiler.backend.wiring.policies.control import ControlFlowWiringPolicy
from cascade.compiler.backend.wiring.policies.observability import (
    ObservabilityWiringPolicy,
)
from cascade.compiler.backend.wiring.policies.resource import ResourceWiringPolicy
from cascade.compiler.backend.wiring.policies.pulse import PulseWiringPolicy
from cascade.spec.physical.constants import NodePrefix


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()
        self._expansion_policies: List[ExpansionPolicy] = []
        self._wiring_policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]

    def build(
        self, graph_ir: GraphIR, environment: EnvironmentDef
    ) -> CompilationArtifact:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        # For now, ExpansionContext and WiringContext are identical.
        # We use a single context object for both phases.
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )
        symbol_table = {}

        # 2. Phase 0: Setup Global Infrastructure (for wiring policies)
        for policy in self._wiring_policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Materialization (Expansion)
        # Create all nodes for all subgraphs, but do not connect them across boundaries.
        for node_ir in graph_ir.nodes:
            # 3.1 Expand core triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.current_node_instance_hash, subgraph)

            # 3.2 Populate Symbol Table from core triad
            if subgraph.worker:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.worker.id] = canonical_hash

            # 3.3 Apply expansion policies to create auxiliary nodes
            for policy in self._expansion_policies:
                policy.expand(ctx, node_ir, subgraph)

        # 4. Phase 2: Wiring
        # Connect all the created nodes together.
        for node_ir in graph_ir.nodes:
            subgraph = ctx.get_subgraph(node_ir.current_node_instance_hash)
            for policy in self._wiring_policies:
                policy.apply(ctx, node_ir, subgraph)

        # 5. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        # 6. Generate Manifest
        logical_to_physical_map = {}
        for node_ir in graph_ir.nodes:
            if node_ir.logical_id:
                logical_to_physical_map[node_ir.logical_id] = (
                    node_ir.current_node_instance_hash
                )

        assembly = Assembly(
            graph=physical_graph,
            symbol_table=symbol_table,
            metadata={"compiler": "cascade-compiler-v0.1.0"},
        )
        entry_points = [
            node_id
            for node_id, node in physical_graph.nodes.items()
            if isinstance(node, PhysicsDataNode)
            and (
                node_id.startswith(f"{NodePrefix.CONST}.")
                or node_id.startswith(f"{NodePrefix.PULSE}.")
            )
        ]
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode)
            and node.id.startswith(f"{NodePrefix.EGRESS}.")
        }

        manifest = CompilationManifest(
            logical_to_physical_map=logical_to_physical_map,
            entry_points=sorted(entry_points),
            exit_points=exit_points,
        )

        return CompilationArtifact(assembly=assembly, manifest=manifest)