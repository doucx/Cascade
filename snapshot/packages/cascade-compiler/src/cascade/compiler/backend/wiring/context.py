from dataclasses import dataclass, field
from typing import Dict

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.ir.graph import GraphIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.harness import WiringHarness


@dataclass
class WiringContext:
    graph_ir: GraphIR
    environment: EnvironmentDef
    physical_graph: BipartiteGraph
    wire: WiringHarness
    subgraphs: Dict[str, SubGraph] = field(default_factory=dict)

    def register_subgraph(self, node_id: str, subgraph: SubGraph) -> None:
        self.subgraphs[node_id] = subgraph
        self.wire.add_subgraph(subgraph)

    def get_subgraph(self, node_id: str) -> SubGraph:
        if node_id not in self.subgraphs:
            raise KeyError(f"Subgraph for node '{node_id}' not found in context.")
        return self.subgraphs[node_id]
