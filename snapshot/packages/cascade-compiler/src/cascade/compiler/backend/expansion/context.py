from __future__ import annotations

from dataclasses import dataclass, field

from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.topology import BipartiteGraph

from ..expander import SubGraph
from ..wiring import WiringHarness


@dataclass
class ExpansionContext:
    graph_ir: GraphIR
    environment: EnvironmentDef
    physical_graph: BipartiteGraph
    wire: WiringHarness
    subgraphs: dict[str, SubGraph] = field(default_factory=dict)
