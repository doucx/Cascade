from dataclasses import dataclass
from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    """
    The Launcher is the first half of the Dyad.
    It prepares the context, aggregates arguments, and dispatches the compute request.
    """
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""
    
    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""


@dataclass
class LanderNode(PhysicsFuncNode):
    """
    The Lander is the second half of the Dyad.
    It receives the result, finalizes the lifecycle, and handles routing.
    """
    pass