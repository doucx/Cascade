from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import itertools

# Fast, thread-safe counter for event IDs
_event_id_gen = itertools.count()


@dataclass(frozen=True)
class Event:
    event_id: str = field(default_factory=lambda: str(next(_event_id_gen)))
    timestamp: float = field(default_factory=time.time)

    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None


@dataclass(frozen=True)
class RunStarted(Event):
    # Must provide defaults because base class has defaults
    target_tasks: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunFinished(Event):
    status: str = "Unknown"  # "Succeeded", "Failed"
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
    status: str = "Unknown"  # "Succeeded", "Failed"
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    reason: str = "Unknown"  # "CacheHit", "ConditionFalse"


@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    reason: str = "Unknown"  # e.g. "RateLimit", "ConcurrencyLimit"


@dataclass(frozen=True)
class StaticAnalysisWarning(TaskEvent):
    warning_code: str = ""  # e.g. "CS-W001"
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


# --- Tooling Events ---


@dataclass(frozen=True)
class ToolEvent(Event):
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    target_node_id: str = ""

    def _get_payload(self) -> Dict[str, Any]:
        return {"target_node_id": self.target_node_id}


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "input_bindings": self.input_bindings,
        }


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    total_steps: int = 0

    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}
