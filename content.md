现在开始执行 **Cascade Bus 逻辑迁移**。我们将按照“外科手术”式的方法，将 `EventBus` 和 `FeedbackBus` 的核心实现从 `runtime` 和 `common` 中剥离，统一安置在 `cascade-bus` 包中。

## [WIP] 开始执行 Cascade Bus 逻辑迁移

## 标签
#intent/refine #flow/ready #priority/high
#comp/engine #comp/runtime #comp/common #comp/bus #concept/ui
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 迁移 `FeedbackBus` 与 `MessageStore` (来自 `common`)

我们将 `cascade-common` 中的消息总线逻辑迁移到 `cascade-bus`。

~~~~~act
write_file
packages/cascade-bus/src/cascade/bus/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Any


class Renderer(Protocol):
    def render(self, msg_id: str, level: str, **kwargs: Any) -> None: ...
~~~~~

~~~~~act
write_file
packages/cascade-bus/src/cascade/bus/messages.py
~~~~~
~~~~~python
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: Dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Optional[Path]:
        try:
            # 这里的路径调整为相对于 cascade.bus 包
            locales_path = Path(__file__).parent / "locales"
            if locales_path.is_dir():
                return locales_path
        except Exception:
            pass
        return None

    def _load_messages(self):
        locales_dir = self._find_locales_dir()
        if not locales_dir:
            logger.error("Message resource directory 'locales' not found.")
            return

        locale_path = locales_dir / self.locale
        if not locale_path.is_dir():
            return

        for message_file in locale_path.glob("*.json"):
            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    self._messages.update(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load message file {message_file}: {e}")

    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"
~~~~~

~~~~~act
write_file
packages/cascade-bus/src/cascade/bus/feedback.py
~~~~~
~~~~~python
from typing import Any, Optional
from .messages import MessageStore
from .protocols import Renderer


class FeedbackBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
_default_store = MessageStore(locale="en")
bus = FeedbackBus(store=_default_store)
~~~~~

#### Acts 2: 迁移 `EventBus` 与 `Events` (来自 `runtime`)

我们将 `cascade-runtime` 中的观测性事件和总线逻辑迁移到 `cascade-bus`。

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
~~~~~

~~~~~act
write_file
packages/cascade-bus/src/cascade/bus/core.py
~~~~~
~~~~~python
from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from cascade.spec import EventIR
from .events import Event

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Handler]] = defaultdict(list)
        self._wildcard_subscribers: List[Handler] = []

    def subscribe(self, event_type: Type[Event], handler: Handler):
        if event_type is Event:
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        for handler in self._wildcard_subscribers:
            handler(event)

    def publish_ir(self, ir: EventIR):
        event = Event.from_ir(ir)
        self.publish(event)
~~~~~

#### Acts 3: 迁移资源文件 (Locales)

我们需要将多语言资源文件移动到 `cascade-bus` 中。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-bus/src/cascade/bus/locales
cp -r packages/cascade-common/src/cascade/common/locales/* packages/cascade-bus/src/cascade/bus/locales/
~~~~~

#### Acts 4: 降级 `cascade-common` 与 `cascade-runtime` (Thin Wrappers)

现在我们将原来的 Bus 位置变成对新包的引用。

~~~~~act
write_file
packages/cascade-common/src/cascade/common/messaging/bus.py
~~~~~
~~~~~python
# Thin wrapper for backward compatibility
from cascade.bus.feedback import FeedbackBus, MessageStore, bus

__all__ = ["bus", "FeedbackBus", "MessageStore"]
~~~~~

~~~~~act
write_file
packages/cascade-common/src/cascade/common/messaging/protocols.py
~~~~~
~~~~~python
from cascade.bus.protocols import Renderer
__all__ = ["Renderer"]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/services/observability/bus.py
~~~~~
~~~~~python
from cascade.bus.core import EventBus, Handler
__all__ = ["EventBus", "Handler"]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python
from cascade.bus.events import (
    Event, RunStarted, RunFinished, TaskEvent, TaskExecutionStarted,
    TaskExecutionFinished, TaskSkipped, TaskRetrying, TaskBlocked,
    StaticAnalysisWarning, ResourceEvent, ResourceAcquired, ResourceReleased,
    ConnectorConnected, ConnectorDisconnected
)
# Re-export everything to maintain API compatibility
__all__ = [
    "Event", "RunStarted", "RunFinished", "TaskEvent", "TaskExecutionStarted",
    "TaskExecutionFinished", "TaskSkipped", "TaskRetrying", "TaskBlocked",
    "StaticAnalysisWarning", "ResourceEvent", "ResourceAcquired", "ResourceReleased",
    "ConnectorConnected", "ConnectorDisconnected"
]
~~~~~

#### Acts 5: 清理工作

~~~~~act
run_command
~~~~~
~~~~~
rm -rf packages/cascade-common/src/cascade/common/locales
~~~~~

### 下一步建议

我们已经成功地将 Cascade 内部的所有总线逻辑“孤立”到了 `cascade-bus` 中，并保持了现有代码的兼容性。

接下来的逻辑演进方向是：
1.  **Stitcher 迁移**: 对 `stitcher` 进行同样的剥离操作。
2.  **创建 `pyneedle-bus`**: 开始实现统一的总线内核，并让 `cascade-bus` 继承它。
3.  **全局重构**: 一切就绪后，通过 `stitcher refactor` 将所有 `from cascade.bus...` 替换为 `from pyneedle.bus...`。

如果你想继续，我们可以开始对 `stitcher` 进行同样的操作，或者直接开始构建 `pyneedle-bus` 内核。
