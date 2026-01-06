from dataclasses import dataclass
from cascade.spec.physical.nodes import PhysicsFuncNode


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
