from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time

@dataclass(frozen=True)
class Event:
    """Base class for all runtime events."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None

@dataclass(frozen=True)
class RunStarted(Event):
    """Fired when the engine starts a new run."""
    target_tasks: List[str]
    params: Dict[str, Any]

@dataclass(frozen=True)
class RunFinished(Event):
    """Fired when the engine finishes a run."""
    status: str  # "Succeeded", "Failed"
    duration: float
    error: Optional[str] = None

@dataclass(frozen=True)
class TaskEvent(Event):
    """Base for events related to a specific task instance."""
    task_id: str
    task_name: str

@dataclass(frozen=True)
class TaskExecutionStarted(TaskEvent):
    """Fired just before a task's function is executed."""
    pass

@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    """Fired after a task's function finishes, successfully or not."""
    status: str # "Succeeded", "Failed"
    duration: float
    result_preview: Optional[str] = None
    error: Optional[str] = None

@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""
    reason: str  # "CacheHit", "ConditionFalse"