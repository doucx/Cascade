from dataclasses import dataclass
from cascade.spec.physical.nodes import PhysicsFuncNode


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
