from dataclasses import dataclass
from .nodes import PhysicsFuncNode


@dataclass
class ObservabilityNode(PhysicsFuncNode):
    pass


@dataclass
class RetryNode(PhysicsFuncNode):
    max_attempts: int = 3
    # Future: delay, backoff, etc.