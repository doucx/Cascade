from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import itertools
import logging

from cascade.spec import EventIR, EventType, EventState

logger = logging.getLogger(__name__)

# Fast, thread-safe counter for event IDs
_event_id_gen = itertools.count()


@dataclass(frozen=True)
class Event:
    event_id: str = field(default_factory=lambda: str(next(_event_id_gen)))
    timestamp: float = field(default_factory=time.time)
    run_id: Optional[str] = None

    @staticmethod
    def from_ir(ir: EventIR) -> "Event":
        return _from_ir(ir)


@dataclass(frozen=True)
class RunStarted(Event):
    target_tasks: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunFinished(Event):
    status: EventState = EventState.SUCCEEDED
    duration: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskEvent(Event):
    task_id: str = ""
    task_name: str = ""


@dataclass(frozen=True)
class TaskExecutionStarted(TaskEvent):
    pass


@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    status: EventState = EventState.SUCCEEDED
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    reason: str = "Unknown"


@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    reason: str = "Unknown"


@dataclass(frozen=True)
class StaticAnalysisWarning(TaskEvent):
    warning_code: str = ""
    message: str = ""


@dataclass(frozen=True)
class ResourceEvent(Event):
    resource_name: str = ""


@dataclass(frozen=True)
class ResourceAcquired(ResourceEvent):
    pass


@dataclass(frozen=True)
class ResourceReleased(ResourceEvent):
    pass


@dataclass(frozen=True)
class ConnectorConnected(Event):
    pass


@dataclass(frozen=True)
class ConnectorDisconnected(Event):
    pass


# --- Hydration Logic ---

def _from_ir(ir: EventIR) -> "Event":
    try:
        ctx = ir.get("ctx", {})
        run_id = ctx.get("rid")
        timestamp = ir["ts"]
        event_type = ir["t"]

        if event_type == EventType.LIFECYCLE:
            return _hydrate_lifecycle(ir, run_id, timestamp)

        return Event(timestamp=timestamp, run_id=run_id)
    except Exception as e:
        logger.warning(f"Failed to hydrate EventIR: {e}")
        return Event()


def _hydrate_lifecycle(ir: EventIR, run_id: Optional[str], timestamp: float) -> "TaskEvent":
    data = ir["data"]
    phy = ir.get("phy", {})
    task_id = data.get("task_id", phy.get("nid", ""))
    task_name = data.get("task_name", "unknown")
    state_raw = data.get("state")

    base_kwargs = {
        "timestamp": timestamp,
        "run_id": run_id,
        "task_id": task_id,
        "task_name": task_name,
    }

    if not state_raw:
        return TaskEvent(**base_kwargs)
    try:
        state = EventState(state_raw)
    except ValueError:
        return TaskEvent(**base_kwargs)

    if state == EventState.RUNNING:
        return TaskExecutionStarted(**base_kwargs)
    if state in (EventState.SUCCEEDED, EventState.FAILED):
        duration_sec = data.get("duration_ms", 0.0) / 1000.0
        return TaskExecutionFinished(
            **base_kwargs, status=state, duration=duration_sec,
            error=data.get("error"), result_preview=data.get("result_preview")
        )
    if state == EventState.SKIPPED:
        return TaskSkipped(**base_kwargs, reason=data.get("reason", "Unknown"))

    return TaskEvent(**base_kwargs)