from dataclasses import dataclass
from .physics import PhysicsFuncNode


@dataclass
class BleachNode(PhysicsFuncNode):
    """
    F_pre: The Pre-process Node.
    Responsible for:
    1. Waiting for all inputs (Data, Control, Resources).
    2. 'Bleaching' tokens: stripping metadata to extract pure payload.
    3. Emitting start events to the sidecar observation channel.
    """

    pass


@dataclass
class WorkerNode(PhysicsFuncNode):
    """
    F_exec: The Execution Node.
    Responsible for:
    1. Executing the pure business logic (Python function).
    2. Producing a pure result.
    It is completely unaware of tags, traces, or the graph topology.
    """

    pass


@dataclass
class StainNode(PhysicsFuncNode):
    """
    F_post: The Post-process Node.
    Responsible for:
    1. 'Staining' the result: wrapping it into a new Token with tags and trace info.
    2. Routing based on results (setting tags).
    3. Emitting end events to the sidecar observation channel.
    """

    pass


@dataclass
class ObservabilityNode(PhysicsFuncNode):
    """
    F_obs: The Sidecar Observer.
    Responsible for converting raw trace tokens into standardized telemetry events
    and publishing them to the external message bus.
    """

    pass