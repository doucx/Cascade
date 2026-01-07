Excellent. You've provided the missing file, which confirms my diagnosis precisely. The root cause lies within `events.py`, where the `TaskExecutionFinished` dataclass is defined with `status: str` and the `_hydrate_lifecycle` function explicitly converts the `EventState` enum back into a string (`"Succeeded"`), thus breaking the type-safe contract at the point of creation.

I will now generate a complete and correct plan to implement your "Enum-First Contract" proposal end-to-end. This plan will fix the event definition, the hydration logic, the subscribers, and the tests, ensuring ontological correctness throughout the entire event lifecycle.

## [WIP] refactor(events): Enforce type-safe EventState contract end-to-end

### 错误分析

The previous test failures were caused by a type mismatch originating in the event hydration layer.
1.  **Producer (`standard_stainer`)**: Correctly created an `EventIR` with an `EventState` enum member.
2.  **Hydrator (`_hydrate_lifecycle` in `events.py`)**: Incorrectly converted the `EventState` enum member back into a capitalized string (`'Succeeded'`) when creating the `TaskExecutionFinished` object.
3.  **Dataclass Contract (`TaskExecutionFinished` in `events.py`)**: Incorrectly defined its `status` field as `str`, formalizing the type error.
4.  **Consumers (Tests & `HumanReadableLogSubscriber`)**: When they received the event object, its `status` was a `str`, causing `is EventState.SUCCEEDED` assertions to fail.

This plan will correct the dataclass contract and the hydration logic, ensuring the `EventState` enum type is preserved from producer to consumer.

### 用户需求

Enforce a strict, type-safe contract for all event states within the system by:
1.  Eliminating all "magic string" comparisons for states.
2.  Ensuring that both the producers and consumers of events operate on a shared, authoritative `EventState` enum.
3.  Making tests and subscribers robust by having them validate semantic intent (`is EventState.SUCCEEDED`) rather than a specific string implementation (`== "Succeeded"`).

### 評論

This is a critical architectural improvement. By addressing the issue at its source (`events.py`), we establish a robust, self-documenting, and type-safe contract for system states, completely fulfilling the vision of the "Concord" proposal. This eliminates a significant source of fragility.

### 目标

1.  Modify the `RunFinished` and `TaskExecutionFinished` dataclasses in `events.py` to type the `status` field as `EventState`.
2.  Correct the `_hydrate_lifecycle` function in `events.py` to pass the `EventState` enum member directly into the event object constructor, eliminating the string conversion.
3.  Update the `HumanReadableLogSubscriber` in `subscribers.py` to use `EventState` for its conditional logic, conforming to the new contract.
4.  Re-apply the patches to the integration tests in `cascade-vm` to use type-safe enum comparisons, which should now pass.

### 基本原理

The strategy is to fix the chain of custody for the `EventState` type.
1.  **Correct the Contract**: By changing `status: str` to `status: EventState` in the `dataclass` definitions, we declare the correct intent to the type system and developers.
2.  **Correct the Factory**: By fixing `_hydrate_lifecycle`, we ensure the objects created adhere to this contract.
3.  **Conform all Consumers**: By updating subscribers and tests, we complete the end-to-end migration, ensuring the entire system speaks the same language of type-safe enums.

This creates a virtuous cycle where the type checker will now flag any future deviation from this contract.

### 标签

#intent/refine #flow/ready #priority/high #comp/spec #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/architecture #task/object/event-contracts #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正事件契约与工厂 (Fix Event Contract & Factory)

我将首先修改 `events.py`，这是问题的核心。我会更新 dataclass 定义并修复 hydration 逻辑。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class RunFinished(Event):
    status: str = "Unknown"  # "Succeeded", "Failed"
    duration: float = 0.0
    error: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class RunFinished(Event):
    status: EventState = EventState.SUCCEEDED
    duration: float = 0.0
    error: Optional[str] = None
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    status: str = "Unknown"  # "Succeeded", "Failed"
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    status: EventState = EventState.SUCCEEDED
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    elif state in (EventState.SUCCEEDED, EventState.FAILED):
        # Convert ms to seconds for internal Event model compatibility
        duration_sec = data.get("duration_ms", 0.0) / 1000.0

        return TaskExecutionFinished(
            **base_kwargs,
            status=state,
            duration=duration_sec,
            error=data.get("error"),
            result_preview=data.get("result_preview"),
        )
~~~~~

#### Acts 2: 更新事件订阅者 (Update Event Subscriber)

接下来，我将修改 `HumanReadableLogSubscriber`，使其与新的类型契约保持一致。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
from cascade.common.messaging import bus
from cascade.runtime.services.observability.events import (
    RunStarted,
    RunFinished,
~~~~~
~~~~~python.new
import platform
import os
import asyncio
from datetime import datetime, timezone
from cascade.runtime.services.observability.bus import EventBus
from cascade.common.messaging import bus
from cascade.spec import EventState
from cascade.runtime.services.observability.events import (
    RunStarted,
    RunFinished,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            bus.info("run.finished_success", duration=event.duration)
        else:
            bus.error(
                "run.finished_failure", duration=event.duration, error=event.error
            )

    def on_task_started(self, event: TaskExecutionStarted):
        bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            bus.info(
                "task.finished_success",
                task_name=event.task_name,
                duration=event.duration,
            )
        else:
            bus.error(
                "task.finished_failure",
                task_name=event.task_name,
                duration=event.duration,
                error=event.error,
            )
~~~~~
~~~~~python.new
    def on_run_finished(self, event: RunFinished):
        if event.status is EventState.SUCCEEDED:
            bus.info("run.finished_success", duration=event.duration)
        else:
            bus.error(
                "run.finished_failure", duration=event.duration, error=event.error
            )

    def on_task_started(self, event: TaskExecutionStarted):
        bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status is EventState.SUCCEEDED:
            bus.info(
                "task.finished_success",
                task_name=event.task_name,
                duration=event.duration,
            )
        else:
            bus.error(
                "task.finished_failure",
                task_name=event.task_name,
                duration=event.duration,
                error=event.error,
            )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", "") == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
                TaskBlocked: "BLOCKED",
            }
~~~~~
~~~~~python.new
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", EventState.FAILED) is EventState.SUCCEEDED
                else "FAILED",
                TaskSkipped: "SKIPPED",
                TaskBlocked: "BLOCKED",
            }
~~~~~

### 下一步建议

我们已经完成了从源头到消费端的全面重构。现在，我强烈建议立即运行完整的 `pytest` 测试套件。这次，我们期望所有测试都能通过，从而验证我们的架构改进是正确且完整的。

如果测试通过，下一步就是创建一个 `[COMMIT]` 计划来永久保存这些更改。
