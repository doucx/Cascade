好的，我来修复这些 `pyright` 静态分析错误。

这些错误主要分为两类：
1.  **类型不匹配**：向期望 `EventState` 枚举成员的函数传递了原始字符串（例如 `"Succeeded"` 而不是 `EventState.SUCCEEDED`）。
2.  **API 不匹配**：在 `serialize.py` 中，`MapNode` 的构造函数调用了一个已被移除的参数 `mapping_factory`。
3.  **类型推断问题**：在 `events.py` 中，`pyright` 无法正确地将一个可能为 `None` 的变量在 `if` 块内收窄为非 `None` 类型，需要更健壮的类型转换逻辑。

我将生成一个计划来逐一修复这些问题。

## [WIP] fix(runtime): Correct pyright type errors in runtime package

### 用户需求

修复 `pyright` 在 `packages/cascade-runtime` 中报告的所有静态分析错误。

### 评论

这是一个必要的修复，可以提高代码的健壮性和类型安全性，确保与 `pyright` 的严格检查兼容。这些修复遵循了最佳实践，例如使用枚举成员代替魔法字符串，并确保反序列化逻辑与数据模型保持同步。

### 目标

1.  在 `instance.py` 和 `processor.py` 中，使用 `EventState` 枚举成员替换硬编码的字符串状态。
2.  在 `serialize.py` 中，移除对 `MapNode` 构造函数中已废弃的 `mapping_factory` 参数的调用。
3.  在 `events.py` 中，重构事件水合逻辑，以安全地将来自 `EventIR` 的原始字符串状态转换为 `EventState` 枚举，解决类型推断问题。

### 基本原理

我们将逐个文件进行修复：
-   **`instance.py` & `processor.py`**: 导入 `EventState` 枚举并替换字符串字面量。这是最直接的类型安全修复。
-   **`serialize.py`**: 数据模型 `MapNode` 已经更新，不再直接存储 `mapping_factory`（因为它在运行时从 `ExecutableRegistry` 获取）。反序列化代码必须遵循此模型，因此移除该参数。
-   **`events.py`**: `EventIR` 中的数据是外部输入，可能格式不正确或缺失。我们将添加一个安全的转换层，使用 `try/except` 块将原始字符串转换为 `EventState` 枚举，这既可以处理无效值，也可以向类型检查器提供明确的类型信息，从而解决错误。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `serialize.py`

首先，我们移除对 `MapNode` 构造函数中已废弃的 `mapping_factory` 参数的调用，以匹配其当前定义。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/serialize.py
~~~~~
~~~~~python.old
        node = MapNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="map",
            mapping_factory=_load_func_from_path(data.get("mapping_factory")),
            retry_policy=retry_policy,
            cache_policy=None,  # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
~~~~~
~~~~~python.new
        node = MapNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="map",
            retry_policy=retry_policy,
            cache_policy=None,  # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
~~~~~

#### Acts 2: 修复 `instance.py`

接下来，我们在 `instance.py` 中导入 `EventState` 枚举，并用其成员替换硬编码的字符串。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import (
    RunStarted,
    RunFinished,
~~~~~
~~~~~python.new
from cascade.spec import EventState
from cascade.runtime.services.observability.events import (
    RunStarted,
    RunFinished,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
~~~~~
~~~~~python.new
            self.bus.publish(
                RunFinished(run_id=run_id, status=EventState.SUCCEEDED, duration=duration)
            )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
~~~~~
~~~~~python.new
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status=EventState.FAILED,
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
~~~~~

#### Acts 3: 修复 `processor.py`

同样，我们修复 `processor.py` 中的类型不匹配问题。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/processor.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
~~~~~
~~~~~python.new
from cascade.spec import EventState
from cascade.runtime.services.observability.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/processor.py
~~~~~
~~~~~python.old
        self.bus.publish(
            TaskExecutionFinished(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
                status="Succeeded",
                duration=duration,
                result_preview=None,
            )
        )
~~~~~
~~~~~python.new
        self.bus.publish(
            TaskExecutionFinished(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
                status=EventState.SUCCEEDED,
                duration=duration,
                result_preview=None,
            )
        )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/processor.py
~~~~~
~~~~~python.old
            self.bus.publish(
                TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    status="Failed",
                    duration=duration,
                    error=f"{type(exception).__name__}: {exception}",
                )
            )
~~~~~
~~~~~python.new
            self.bus.publish(
                TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    status=EventState.FAILED,
                    duration=duration,
                    error=f"{type(exception).__name__}: {exception}",
                )
            )
~~~~~

#### Acts 4: 修复 `events.py`

最后，我们重构 `_hydrate_lifecycle` 函数，以稳健地处理来自 `EventIR` 的状态值，解决 `pyright` 的类型推断错误。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python.old
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
        # Convert ms to seconds for internal Event model compatibility
        duration_sec = data.get("duration_ms", 0.0) / 1000.0

        return TaskExecutionFinished(
            **base_kwargs,
            status=state,
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
~~~~~
~~~~~python.new
def _hydrate_lifecycle(
    ir: EventIR, run_id: Optional[str], timestamp: float
) -> "TaskEvent":
    data = ir["data"]
    phy = ir.get("phy", {})

    # Prefer logical IDs from data, fallback to physical IDs
    task_id = data.get("task_id", phy.get("nid", ""))
    task_name = data.get("task_name", "unknown")

    # Safely convert raw state string to EventState enum
    state_raw = data.get("state")
    state: Optional[EventState] = None
    if state_raw:
        try:
            state = EventState(state_raw)
        except ValueError:
            logger.warning(f"Unknown EventState '{state_raw}' in EventIR data.")

    base_kwargs = {
        "timestamp": timestamp,
        "run_id": run_id,
        "task_id": task_id,
        "task_name": task_name,
    }

    if state == EventState.RUNNING:
        return TaskExecutionStarted(**base_kwargs)

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
~~~~~

### 下一步建议

所有已报告的 `pyright` 错误都已修复。建议再次运行 `pyright packages/cascade-runtime` 来验证修复是否完全解决了问题。之后，可以继续处理其他软件包或提交这些更改。
