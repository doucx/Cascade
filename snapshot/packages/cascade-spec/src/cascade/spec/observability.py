from enum import StrEnum
from typing import TypedDict, Dict, Any, Optional


class EventType(StrEnum):
    """
    Standard taxonomy for Cascade telemetry events.
    Aligned with OpenTelemetry semantic conventions where possible.
    """
    LIFECYCLE = "task.lifecycle"
    RESOURCE = "resource.usage"
    DATA = "data.flow"
    ERROR = "system.error"
    CUSTOM = "custom.event"


class EventState(StrEnum):
    """
    Standard lifecycle states for tasks and workflows.
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PhysicalAnchor(TypedDict):
    """
    Physical location metadata identifying where the event originated in the topology.
    """
    nid: str  # Node ID (The physical node hash)


class EventContext(TypedDict, total=False):
    """
    Logical context injected by the environment.
    This metadata is orthogonal to the physical topology.
    """
    rid: str  # Run ID
    pid: str  # Project ID
    uid: str  # User/Org ID


class EventIR(TypedDict):
    """
    The Intermediate Representation of an Observability Event.
    Designed to be a flat, JSON-serializable dictionary (The 'Hologram').
    
    Structure:
    - Header: Protocol metadata (v, t, ts)
    - Context (ctx): Logical environment info
    - Physics (phy): Physical topology info
    - Data (data): The actual payload
    """
    v: str            # Protocol Version: "1.0"
    t: str            # Event Type (EventType)
    ts: float         # Unix Timestamp (when it happened physically)
    
    ctx: EventContext
    phy: PhysicalAnchor
    
    data: Dict[str, Any]