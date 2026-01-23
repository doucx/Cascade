from dataclasses import dataclass, field
from typing import List, Set
from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""

    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""

    # Metadata to reconstruct arguments correctly
    arg_port_names: List[str] = field(default_factory=list)
    kwarg_port_names: Set[str] = field(default_factory=set)


@dataclass
class LanderNode(PhysicsFuncNode):
    pass
