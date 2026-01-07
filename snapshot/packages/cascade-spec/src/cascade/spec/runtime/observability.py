from enum import StrEnum
from typing import TypedDict, Dict, Any


class EventType(StrEnum):
    LIFECYCLE = "task.lifecycle"
    RESOURCE = "resource.usage"
    DATA = "data.flow"
    ERROR = "system.error"
    CUSTOM = "custom.event"


class EventState(StrEnum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"


class PhysicalAnchor(TypedDict):
    nid: str  # Node ID (The physical node hash)


class EventContext(TypedDict, total=False):
    rid: str  # Run ID
    pid: str  # Project ID
    uid: str  # User/Org ID


class EventIR(TypedDict):
    v: str  # Protocol Version: "1.0"
    t: str  # Event Type (EventType)
    ts: float  # Unix Timestamp (when it happened physically)

    ctx: EventContext
    phy: PhysicalAnchor

    data: Dict[str, Any]
