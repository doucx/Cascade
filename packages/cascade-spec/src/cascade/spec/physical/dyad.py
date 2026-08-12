from dataclasses import dataclass

from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""

    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""


@dataclass
class LanderNode(PhysicsFuncNode):
    pass
