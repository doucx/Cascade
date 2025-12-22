from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class TelemetryHeader:
    """Standard header for all telemetry messages."""

    v: str = "1.0"
    ts: str = ""  # ISO 8601 UTC timestamp
    run_id: str = ""
    org_id: str = "local"
    project_id: str = "default"
    source: str = ""  # e.g., "worker-hostname-pid"


@dataclass(frozen=True)
class LifecycleEvent:
    """Represents engine lifecycle events."""

    event: str  # "ENGINE_STARTED", "ENGINE_STOPPED"


@dataclass(frozen=True)
class TaskStateEvent:
    """Represents a change in a task's execution state."""

    task_id: str
    task_name: str
    state: str  # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    duration_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceEvent:
    """Represents an event related to a resource's lifecycle."""

    resource_name: str
    action: str  # ACQUIRE | RELEASE
    current_usage: Dict[str, Any] = field(default_factory=dict)
