from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import itertools

# Fast, thread-safe counter for event IDs
_event_id_gen = itertools.count()


@dataclass(frozen=True)
class Event:
    """Base class for all runtime events."""

    event_id: str = field(default_factory=lambda: str(next(_event_id_gen)))
    timestamp: float = field(default_factory=time.time)

    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None


@dataclass(frozen=True)
class RunStarted(Event):
    """Fired when the engine starts a new run."""

    # Must provide defaults because base class has defaults
    target_tasks: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunFinished(Event):
    """Fired when the engine finishes a run."""

    status: str = "Unknown"  # "Succeeded", "Failed"
    duration: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskEvent(Event):
    """Base for events related to a specific task instance."""

    task_id: str = ""
    task_name: str = ""


@dataclass(frozen=True)
class TaskExecutionStarted(TaskEvent):
    """Fired just before a task's function is executed."""

    pass


@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    """Fired after a task's function finishes, successfully or not."""

    status: str = "Unknown"  # "Succeeded", "Failed"
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""

    reason: str = "Unknown"  # "CacheHit", "ConditionFalse"


@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    """Fired when a task fails but is about to be retried."""

    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    """Fired when a task is deferred due to constraint violations."""

    reason: str = "Unknown"  # e.g. "RateLimit", "ConcurrencyLimit"


@dataclass(frozen=True)
class StaticAnalysisWarning(TaskEvent):
    """Fired when static analysis detects a potential issue."""

    warning_code: str = ""  # e.g. "CS-W001"
    message: str = ""


@dataclass(frozen=True)
class ResourceEvent(Event):
    """Base for events related to resources."""

    resource_name: str = ""


@dataclass(frozen=True)
class ResourceAcquired(ResourceEvent):
    """Fired when a resource is successfully initialized (setup complete)."""

    pass


@dataclass(frozen=True)
class ResourceReleased(ResourceEvent):
    """Fired when a resource is successfully torn down."""

    pass


@dataclass(frozen=True)
class ConnectorConnected(Event):
    """Fired when the engine successfully connects to an external connector."""

    pass


@dataclass(frozen=True)
class ConnectorDisconnected(Event):
    """Fired when the engine disconnects from an external connector."""

    pass
