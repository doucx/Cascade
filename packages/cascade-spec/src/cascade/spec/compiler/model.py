from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ..physical.nodes import PhysicsNode, PhysicsDataNode
from ..physical.dyad import LauncherNode, LanderNode
from ..physical.topology import Channel


@dataclass
class SubGraph:
    launcher: Optional[LauncherNode] = None
    lander: Optional[LanderNode] = None

    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
    resources: Dict[str, List[PhysicsNode]] = field(default_factory=dict)
    controls: Dict[str, PhysicsNode] = field(default_factory=dict)

    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)
