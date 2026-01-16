from dataclasses import dataclass
from .nodes import PhysicsFuncNode


@dataclass
class BleachNode(PhysicsFuncNode):
    pass


@dataclass
class WorkerNode(PhysicsFuncNode):
    # The canonical hash of the code this worker is supposed to execute.
    # This is populated by the compiler and used by the standard_dispatcher.
    canonical_code_structure_hash: str = ""


@dataclass
class StainNode(PhysicsFuncNode):
    pass


@dataclass
class ObservabilityNode(PhysicsFuncNode):
    pass


@dataclass
class RetryNode(PhysicsFuncNode):
    max_attempts: int = 3
    # Future: delay, backoff, etc.
