from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class TelemetryHeader:
    v: str = "1.0"
    ts: str = ""  # ISO 8601 UTC timestamp
    run_id: str = ""
    org_id: str = "local"
    project_id: str = "default"
    source: str = ""  # e.g., "worker-hostname-pid"


@dataclass(frozen=True)
class LifecycleEvent:
    event: str  # "ENGINE_STARTED", "ENGINE_STOPPED"


@dataclass(frozen=True)
class TaskStateEvent:
    task_id: str
    task_name: str
    state: str  # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    duration_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceEvent:
    resource_name: str
    action: str  # ACQUIRE | RELEASE
    current_usage: Dict[str, Any] = field(default_factory=dict)
