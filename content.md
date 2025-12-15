## [WIP] feat: 构建运行时可观测性基础设施

### 用户需求
执行 Cascade 阶段一 (MVP) 的第 4 步：
1.  **事件定义**: 定义基类 `Event` 和关键的生命周期事件（Run, Task）。
2.  **消息总线**: 实现 `MessageBus`，支持发布/订阅模式。
3.  **订阅者**: 实现 `HumanReadableLogSubscriber`，用于输出友好的日志。
4.  **测试**: 编写针对事件总线和订阅者的测试。

### 评论
参考了 `pyquipu` 的设计，我们保持了模块的清晰分离。虽然 `pyquipu` 使用基于 Key 的本地化查找，但 `Cascade` 采用更适合自动化引擎的**事件驱动架构**。日志的生成（Human Readable String）被推迟到了 `Subscriber` 这一层，这使得核心引擎只处理纯数据事件，保持了“洋葱架构”的纯净性。

### 目标
1.  创建 `src/cascade/runtime/events.py`
2.  创建 `src/cascade/runtime/bus.py`
3.  创建 `src/cascade/runtime/subscribers.py`
4.  编写 `tests/test_runtime_observability.py`

### 基本原理
*   **不可变事件**: 使用 `@dataclass(frozen=True)` 定义事件，确保事件在传输过程中不被修改。
*   **解耦**: `MessageBus` 不知道具体的事件处理逻辑，只负责分发。
*   **可插拔日志**: `HumanReadableLogSubscriber` 只是众多可能的订阅者之一。

### 标签
#intent/build #flow/ready #priority/high
#task/domain/runtime #task/object/observability #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 定义运行时事件 (Runtime Events)

定义系统中可能发生的所有关键事件。这些事件携带了足够的数据，以便订阅者可以重建现场。

~~~~~act
write_file
src/cascade/runtime/events.py
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: 实现消息总线 (Message Bus)

实现一个轻量级的内存消息总线。

~~~~~act
write_file
src/cascade/runtime/bus.py
~~~~~
~~~~~python
from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from .events import Event

# Define a Handler type alias for clarity
Handler = Callable[[Any], None]

class MessageBus:
    """
    A simple in-memory message bus for dispatching events to subscribers.
    """
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Handler]] = defaultdict(list)
        self._wildcard_subscribers: List[Handler] = []

    def subscribe(self, event_type: Type[Event], handler: Handler):
        """Register a handler for a specific event type."""
        if event_type is Event:
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        """Dispatch an event to all relevant subscribers."""
        # 1. Dispatch to handlers explicitly subscribed to this event type
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        
        # 2. Dispatch to wildcard handlers (subscribed to Event)
        for handler in self._wildcard_subscribers:
            handler(event)
~~~~~

#### Acts 3: 实现可读日志订阅者 (Log Subscriber)

这是 MVP 的核心 UI 部分。它将事件流转换为用户友好的 emoji 日志。

~~~~~act
write_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
import sys
from typing import TextIO
from .bus import MessageBus
from .events import (
    Event, RunStarted, RunFinished, 
    TaskExecutionStarted, TaskExecutionFinished, TaskSkipped
)

class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stdout).
    """
    def __init__(self, bus: MessageBus, stream: TextIO = sys.stdout):
        self._stream = stream
        
        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        targets = ", ".join(event.target_tasks)
        self._print(f"▶️  Starting Run for targets: [{targets}]")
        if event.params:
            self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
        else:
            self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            self._print(f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s")
        else:
            self._print(f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}")

    def on_task_skipped(self, event: TaskSkipped):
        self._print(f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})")
~~~~~

#### Acts 4: 编写测试

验证总线的分发逻辑和订阅者的格式化输出。

~~~~~act
write_file
tests/test_runtime_observability.py
~~~~~
~~~~~python
import io
import pytest
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber

def test_message_bus_dispatch():
    bus = MessageBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    # Subscribe to specific event
    bus.subscribe(RunStarted, handler)
    
    # Publish relevant event
    event1 = RunStarted(target_tasks=["t1"], params={})
    bus.publish(event1)
    
    assert len(received_events) == 1
    assert received_events[0] == event1

    # Publish irrelevant event
    event2 = TaskExecutionFinished(
        task_id="1", task_name="t", status="Succeeded", duration=0.1
    )
    bus.publish(event2)
    
    # Handler should not receive it
    assert len(received_events) == 1

def test_message_bus_wildcard():
    bus = MessageBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    # Subscribe to base Event (wildcard)
    bus.subscribe(Event, handler)
    
    bus.publish(RunStarted(target_tasks=[], params={}))
    bus.publish(TaskExecutionFinished(task_id="1", task_name="t", status="OK", duration=0.0))
    
    assert len(received_events) == 2

def test_human_readable_subscriber():
    bus = MessageBus()
    output = io.StringIO()
    subscriber = HumanReadableLogSubscriber(bus, stream=output)

    # Simulate a flow
    bus.publish(RunStarted(target_tasks=["deploy"], params={"env": "prod"}))
    bus.publish(TaskExecutionFinished(
        task_id="123", 
        task_name="build_image", 
        status="Succeeded", 
        duration=1.23
    ))
    bus.publish(TaskExecutionFinished(
        task_id="124", 
        task_name="deploy_k8s", 
        status="Failed", 
        duration=0.05, 
        error="AuthError"
    ))

    logs = output.getvalue()
    
    assert "▶️  Starting Run" in logs
    assert "env': 'prod'" in logs
    assert "✅ Finished task `build_image` in 1.23s" in logs
    assert "❌ Failed task `deploy_k8s`" in logs
    assert "AuthError" in logs
~~~~~

### 下一步建议
基础设施已经就绪。现在我们需要实现实际的执行逻辑（Adapters），让事件总线能够接收到真实的事件。
建议执行第 5 步：实现核心协议与默认适配器 (`NativeSolver` 和 `LocalExecutor`)。
