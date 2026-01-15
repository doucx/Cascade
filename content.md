非常抱歉，在搬运过程中遗漏了 **Tooling Events** 以及 `Event.from_ir` 的完整静态方法绑定逻辑，这导致了重定向后的 `ImportError`。

我将立即修正 `cascade-bus` 中的 `events.py` 实现，并确保 `runtime` 中的薄封装（wrapper）完整覆盖所有导出的符号。

## [WIP] 修正 `cascade-bus` 中的 `events.py` 实现

## 标签
#intent/fix #flow/ready #priority/critical
#comp/bus #comp/runtime #concept/ui
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/fix-migration #task/state/continue

---

### Script

#### Acts 1: 完整重写 `cascade-bus` 的 `events.py`

我们将补全缺失的 `ToolEvent` 及其子类，并恢复完整的 `_from_ir` 及其后期的静态方法绑定。

~~~~~act
write_file
packages/cascade-bus/src/cascade/bus/events.py
~~~~~
~~~~~python
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

    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None

    @staticmethod
    def from_ir(ir: "EventIR") -> "Event":
        # This is a stub for the type checker. The real implementation is assigned later
        # at the end of the file to break a circular dependency while keeping pyright happy.
        raise NotImplementedError


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


# --- Event Hydration Logic (Late Binding) ---


def _from_ir(ir: EventIR) -> "Event":
    try:
        # Extract Common Metadata
        ctx = ir.get("ctx", {})
        run_id = ctx.get("rid")
        timestamp = ir["ts"]
        event_type = ir["t"]

        if event_type == EventType.LIFECYCLE:
            return _hydrate_lifecycle(ir, run_id, timestamp)

        # Fallback for unknown types
        return Event(timestamp=timestamp, run_id=run_id)
    except Exception as e:
        logger.warning(f"Failed to hydrate EventIR: {e}. Raw: {ir}")
        # Return a generic event to prevent crashing the bus
        return Event()


def _hydrate_lifecycle(
    ir: EventIR, run_id: Optional[str], timestamp: float
) -> "TaskEvent":
    data = ir["data"]
    phy = ir.get("phy", {})

    # Prefer logical IDs from data, fallback to physical IDs
    task_id = data.get("task_id", phy.get("nid", ""))
    task_name = data.get("task_name", "unknown")
    state_raw = data.get("state")

    base_kwargs = {
        "timestamp": timestamp,
        "run_id": run_id,
        "task_id": task_id,
        "task_name": task_name,
    }

    # Early exit for invalid or missing state
    if not state_raw:
        return TaskEvent(**base_kwargs)
    try:
        state = EventState(state_raw)
    except ValueError:
        logger.warning(f"Unknown EventState '{state_raw}' in EventIR data.")
        return TaskEvent(**base_kwargs)

    # --- From this point, `state` is guaranteed to be a valid EventState member ---

    if state == EventState.RUNNING:
        return TaskExecutionStarted(**base_kwargs)

    if state in (EventState.SUCCEEDED, EventState.FAILED):
        # Convert ms to seconds for internal Event model compatibility
        duration_sec = data.get("duration_ms", 0.0) / 1000.0

        return TaskExecutionFinished(
            **base_kwargs,
            status=state,
            duration=duration_sec,
            error=data.get("error"),
            result_preview=data.get("result_preview"),
        )

    if state == EventState.SKIPPED:
        return TaskSkipped(
            **base_kwargs,
            reason=data.get("reason", "Unknown"),
        )

    if state == EventState.PENDING:
        # Map Pending to generic TaskEvent or a specific one if needed later
        return TaskEvent(**base_kwargs)

    # Fallback for any other valid but unhandled state
    return TaskEvent(**base_kwargs)


# Bind the factory method to the Event class
Event.from_ir = staticmethod(_from_ir)
~~~~~

#### Acts 2: 完善 `runtime` 中的 Events 封装

我们将所有缺失的符号添加到 `__all__` 中，确保下游代码可以正确导入。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python
from cascade.bus.events import (
    Event,
    RunStarted,
    RunFinished,
    TaskEvent,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    TaskBlocked,
    StaticAnalysisWarning,
    ResourceEvent,
    ResourceAcquired,
    ResourceReleased,
    ConnectorConnected,
    ConnectorDisconnected,
    ToolEvent,
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)

# Re-export everything to maintain API compatibility
__all__ = [
    "Event",
    "RunStarted",
    "RunFinished",
    "TaskEvent",
    "TaskExecutionStarted",
    "TaskExecutionFinished",
    "TaskSkipped",
    "TaskRetrying",
    "TaskBlocked",
    "StaticAnalysisWarning",
    "ResourceEvent",
    "ResourceAcquired",
    "ResourceReleased",
    "ConnectorConnected",
    "ConnectorDisconnected",
    "ToolEvent",
    "PlanAnalysisStarted",
    "PlanNodeInspected",
    "PlanAnalysisFinished",
]
~~~~~

### 下一步建议
迁移工作已完成补全。你可以通过运行测试（如 `pytest packages/cascade-runtime`）来验证 import 链路是否完全恢复正常。如果测试通过，我们可以继续后续的 `stitcher` 总线剥离或 `pyneedle` 的构建。
