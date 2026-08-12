from __future__ import annotations

from dataclasses import dataclass, field

from .nodes import PhysicsNode


@dataclass
class Channel:
    source_node_id: str

    source_port: str

    target_node_id: str

    target_port: str = "in"


@dataclass
class BipartiteGraph:
    nodes: dict[str, PhysicsNode] = field(default_factory=dict)

    channels: list[Channel] = field(default_factory=list)
