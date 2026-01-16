from dataclasses import dataclass

from ..expander import SubGraph
from ..expansion.context import ExpansionContext


@dataclass
class WiringContext(ExpansionContext):
    def register_subgraph(self, node_id: str, subgraph: SubGraph) -> None:
        self.subgraphs[node_id] = subgraph
        self.wire.add_subgraph(subgraph)

    def get_subgraph(self, node_id: str) -> SubGraph:
        if node_id not in self.subgraphs:
            raise KeyError(f"Subgraph for node '{node_id}' not found in context.")
        return self.subgraphs[node_id]
