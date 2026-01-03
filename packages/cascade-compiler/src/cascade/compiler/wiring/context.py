from dataclasses import dataclass, field
from typing import Dict

from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring import WiringHarness


@dataclass
class WiringContext:
    """
    A shared context object passed through the wiring pipeline.
    It holds the state of the physical graph being built.
    """

    graph_ir: "GraphIR"  # Forward ref to avoid circular import if possible, or use Any
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