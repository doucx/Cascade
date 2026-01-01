from dataclasses import dataclass
from .physics import PhysicsDataNode


@dataclass
class ResourceSlot(PhysicsDataNode):
    """
    A special DataNode that holds 'Permission Tokens' representing system resources
    (e.g., Concurrency Slots, GPU locks).
    Used to implement back-pressure and resource constraints topologically.
    """

    pass
