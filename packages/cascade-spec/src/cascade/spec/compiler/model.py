from __future__ import annotations

from dataclasses import dataclass, field

from ..physical.dyad import LanderNode, LauncherNode
from ..physical.nodes import PhysicsDataNode, PhysicsNode
from ..physical.topology import Channel


@dataclass
class SubGraph:
    launcher: LauncherNode | None = None
    lander: LanderNode | None = None

    constants: dict[str, PhysicsDataNode] = field(default_factory=dict)
    resources: dict[str, list[PhysicsNode]] = field(default_factory=dict)
    controls: dict[str, PhysicsNode] = field(default_factory=dict)

    nodes: dict[str, PhysicsNode] = field(default_factory=dict)
    channels: list[Channel] = field(default_factory=list)
