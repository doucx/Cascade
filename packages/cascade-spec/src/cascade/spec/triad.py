from dataclasses import dataclass
from .physics import PhysicsFuncNode


@dataclass
class BleachNode(PhysicsFuncNode):
    pass


@dataclass
class WorkerNode(PhysicsFuncNode):
    pass


@dataclass
class StainNode(PhysicsFuncNode):
    pass


@dataclass
class ObservabilityNode(PhysicsFuncNode):
    pass
