from dataclasses import dataclass, field
from typing import Dict

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.ir.graph import GraphIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring import WiringHarness


@dataclass
class ExpansionContext:
    graph_ir: GraphIR
    environment: EnvironmentDef
    physical_graph: BipartiteGraph
    wire: WiringHarness
    subgraphs: Dict[str, SubGraph] = field(default_factory=dict)
