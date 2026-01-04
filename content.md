[简要回答]
我们将执行 Phase 2，在 `cascade-engine` 中实现从 `EventIR` 到富 `Event` 对象的翻译层。

## [WIP] feat(engine): 实现 EventIR 到 Event 的翻译层

### 用户需求
根据 [Cascade 3.0 实施路线图 (Phase 2)](docs/实施路线图：Cascade%203.0%20全息投影协议%20(Event%20IR).md)，需要让 Engine 具备理解 `EventIR` 的能力。
具体包括：
1.  在 `Event` 类中增加 `from_ir` 静态工厂方法，实现从扁平字典到 `TaskExecutionStarted` 等富对象的转换。
2.  在 `EventBus` 中增加 `publish_ir` 方法，作为物理层到逻辑层的适配器。

### 评论
这是连接物理 VM（产生 IR）和逻辑 Engine（消费 Event）的关键桥梁。通过在总线入口处进行“水合 (Hydration)”，我们确保了 Engine 内部的订阅者（如 UI 渲染器、状态追踪器）无需修改即可兼容新的物理层架构，实现了平滑过渡。

### 目标
1.  修改 `cascade.runtime.events`，实现 `Event.from_ir` 及其子类调度逻辑。由于 Python 类定义顺序的限制，我们将采用后期绑定的方式实现此工厂方法。
2.  修改 `cascade.runtime.event_bus`，添加 `publish_ir` 接口。
3.  添加单元测试验证转换逻辑的正确性（覆盖 Start, Finish, Skip 等状态）。

### 基本原理
-   **延迟绑定**: 由于 `Event` 是基类，而工厂方法需要返回其子类（如 `TaskExecutionStarted`），为了避免循环引用或定义顺序问题，我们将转换逻辑函数定义在模块末尾，并动态绑定为 `Event` 的静态方法。
-   **数据映射**: 建立 `EventIR.data` 字段与 `TaskEvent` 属性之间的标准映射契约（如 `duration_ms` -> `duration`）。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/history #scope/core #ai/instruct #task/domain/observability #task/object/event-translation #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 Event 翻译逻辑

在 `events.py` 中引入 `cascade-spec` 的类型，并在文件末尾实现转换函数并绑定到 `Event` 类。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/events.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import itertools

# Fast, thread-safe counter for event IDs
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import itertools
import logging

from cascade.spec import EventIR, EventType, EventState

logger = logging.getLogger(__name__)

# Fast, thread-safe counter for event IDs
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/events.py
~~~~~
~~~~~python.old
    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}
~~~~~
~~~~~python.new
    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}


# --- Event Hydration Logic (Late Binding) ---


def _from_ir(ir: EventIR) -> "Event":
    """
    Static factory method to hydrate an EventIR into a rich Event object.
    Bound to Event.from_ir dynamically to handle subclass forward references.
    """
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
    state = data.get("state")

    base_kwargs = {
        "timestamp": timestamp,
        "run_id": run_id,
        "task_id": task_id,
        "task_name": task_name,
    }

    if state == EventState.RUNNING:
        return TaskExecutionStarted(**base_kwargs)

    elif state in (EventState.SUCCEEDED, EventState.FAILED):
        status = "Succeeded" if state == EventState.SUCCEEDED else "Failed"
        # Convert ms to seconds for internal Event model compatibility
        duration_sec = data.get("duration_ms", 0.0) / 1000.0
        
        return TaskExecutionFinished(
            **base_kwargs,
            status=status,
            duration=duration_sec,
            error=data.get("error"),
            result_preview=data.get("result_preview"),
        )

    elif state == EventState.SKIPPED:
        return TaskSkipped(
            **base_kwargs,
            reason=data.get("reason", "Unknown"),
        )
    
    elif state == EventState.PENDING:
         # Map Pending to generic TaskEvent or a specific one if needed later
         return TaskEvent(**base_kwargs)

    # Fallback
    return TaskEvent(**base_kwargs)


# Bind the factory method to the Event class
Event.from_ir = staticmethod(_from_ir)
~~~~~

#### Acts 2: 增强 EventBus

修改 `event_bus.py` 以支持 `publish_ir`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/event_bus.py
~~~~~
~~~~~python.old
from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from .events import Event

# Define a Handler type alias for clarity
~~~~~
~~~~~python.new
from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from cascade.spec import EventIR
from .events import Event

# Define a Handler type alias for clarity
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/event_bus.py
~~~~~
~~~~~python.old
    def publish(self, event: Event):
        # 1. Dispatch to handlers explicitly subscribed to this event type
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)

        # 2. Dispatch to wildcard handlers (subscribed to Event)
        for handler in self._wildcard_subscribers:
            handler(event)
~~~~~
~~~~~python.new
    def publish(self, event: Event):
        # 1. Dispatch to handlers explicitly subscribed to this event type
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)

        # 2. Dispatch to wildcard handlers (subscribed to Event)
        for handler in self._wildcard_subscribers:
            handler(event)

    def publish_ir(self, ir: EventIR):
        """
        Hydrates an EventIR into a rich Event object and publishes it.
        This serves as the translation layer between the raw physical world (IR)
        and the rich logical world (Events).
        """
        # Event.from_ir is dynamically bound in events.py
        # noinspection PyUnresolvedReferences
        event = Event.from_ir(ir)  # type: ignore
        self.publish(event)
~~~~~

#### Acts 3: 添加单元测试

创建测试文件验证翻译逻辑。

~~~~~act
write_file
packages/cascade-engine/tests/unit/test_event_translation.py
~~~~~
~~~~~python
import time
from cascade.spec import EventIR, EventType, EventState
from cascade.runtime.events import (
    Event, 
    TaskExecutionStarted, 
    TaskExecutionFinished, 
    TaskSkipped
)

def test_hydrate_lifecycle_started():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.RUNNING,
            "task_id": "logical-task-1",
            "task_name": "MyTask"
        }
    }
    
    # Verify the dynamically bound method exists and works
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionStarted)
    assert event.run_id == "run-xyz"
    assert event.timestamp == ts
    assert event.task_id == "logical-task-1"
    assert event.task_name == "MyTask"

def test_hydrate_lifecycle_finished_success():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.SUCCEEDED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "duration_ms": 1500.0,
            "result_preview": "42"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionFinished)
    assert event.status == "Succeeded"
    assert event.duration == 1.5  # Verified ms -> s conversion
    assert event.result_preview == "42"
    assert event.error is None

def test_hydrate_lifecycle_finished_failed():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.FAILED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "duration_ms": 100.0,
            "error": "ValueError: boom"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionFinished)
    assert event.status == "Failed"
    assert event.error == "ValueError: boom"

def test_hydrate_lifecycle_skipped():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.SKIPPED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "reason": "ConditionFalse"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskSkipped)
    assert event.reason == "ConditionFalse"

def test_hydrate_unknown_type():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": "unknown.type", # type: ignore
        "ts": ts,
        "ctx": {},
        "phy": {"nid": "n1"},
        "data": {}
    }
    
    event = Event.from_ir(ir)
    
    # Should fallback to base Event
    assert type(event) is Event
    assert event.timestamp == ts
~~~~~

### 下一步建议

完成 Phase 2 后，Engine 已经具备了处理 IR 的能力。接下来我们将进入 **Phase 3: 物理发射源 (The Emitter)**。

这将涉及修改 `cascade-std` 中的标准库组件（`Bleacher`, `Stainer`, `Observer`），让它们开始产生符合新规范的 `EventIR` 数据，而不是旧的非结构化数据。这将是物理层改造的核心步骤。
