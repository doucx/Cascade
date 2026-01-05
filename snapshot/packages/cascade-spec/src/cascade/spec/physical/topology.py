from dataclasses import dataclass, field
from typing import Dict, List
from cascade.spec.physical.nodes import PhysicsNode


@dataclass
class Channel:
    source_node_id: str

    source_port: str

    target_node_id: str

    target_port: str = "in"


@dataclass
class BipartiteGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)

    channels: List[Channel] = field(default_factory=list)
