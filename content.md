简要回答
我们进入 Phase 5：清理与验证。此阶段我们将修复 VM 代码注册的漏洞，增强标准库的遥测语义（填充 `task_name`），并进行端到端的遥测验证。

## [WIP] fix(vm): 修复代码注册漏洞并增强 E2E 遥测语义

### 用户需求
1.  **修复注册漏洞**: `VMExecutionStrategy` 在收集任务代码时，忽略了 `run_if` 条件和 `after` 依赖中的任务。这会导致这些任务在运行时因找不到代码而崩溃。
2.  **增强遥测**: 目前的 `EventIR` 中 `task_name` 缺失（显示为 "unknown"）。需要从物理节点名称中解析出真实任务名。
3.  **E2E 验证**: 确保从 `Engine` 到 `EventBus` 的链路中，`run_id` 和 `task_name` 均正确传递。

### 评论
这是 VM 走向生产就绪的关键一步。完善的遍历逻辑保证了复杂图的执行稳定性，而正确的 `task_name` 则是用户能看懂日志的前提。

### 目标
1.  修改 `VMExecutionStrategy._collect_lazy_results` 以递归遍历 `_condition` 和 `_dependencies`。
2.  更新 `standard_bleacher` 和 `standard_stainer`，从节点名称（如 `Bleach(MyTask)`) 中提取 `MyTask` 作为 `task_name`。
3.  创建 `test_vm_telemetry.py` 验证完整的事件流。

### 基本原理
-   **代码发现**: 静态分析必须覆盖图的所有边缘（包括控制流和依赖边），不仅仅是数据流。
-   **元数据恢复**: 虽然物理层是无状态的，但编译器在生成物理节点名称时保留了逻辑名称（如 `Bleach(Name)`）。我们可以利用这一约定在运行时“水合”出业务语义。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/engine #comp/std #scope/core #task/domain/observability #task/object/telemetry #task/action/cleanup #task/state/begin

---

### Script

#### Acts 1: 修复 VM 策略的代码收集逻辑

我们将修改 `VMExecutionStrategy`，使其能够递归地发现 `condition` 和 `dependencies` 中的 `LazyResult`，防止因代码未注册导致的运行时错误。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        if isinstance(target, (LazyResult, MappedLazyResult)):
            results[target._uuid] = target
            for arg in target.args:
                results.update(self._collect_lazy_results(arg))
            for k, v in target.kwargs.items():
                results.update(self._collect_lazy_results(v))
        elif isinstance(target, (list, tuple)):
~~~~~
~~~~~python.new
        if isinstance(target, (LazyResult, MappedLazyResult)):
            results[target._uuid] = target
            for arg in target.args:
                results.update(self._collect_lazy_results(arg))
            for k, v in target.kwargs.items():
                results.update(self._collect_lazy_results(v))

            # Traverse Control Flow & Dependencies
            if target._condition:
                results.update(self._collect_lazy_results(target._condition))
            for dep in target._dependencies:
                results.update(self._collect_lazy_results(dep))

        elif isinstance(target, (list, tuple)):
~~~~~

#### Acts 2: 增强 Bleacher 的遥测语义

更新 `standard_bleacher`，尝试从物理节点名称中解析出逻辑任务名。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    logical_id = node.id.replace(".bleach", "")

    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            # We don't have task_name easily here yet, will address in Phase 4
        },
    }
~~~~~
~~~~~python.new
    logical_id = node.id.replace(".bleach", "")

    # Heuristic: Extract task_name from physical name "Bleach(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Bleach(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }
~~~~~

#### Acts 3: 增强 Stainer 的遥测语义

同样更新 `standard_stainer`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    # Determine Status (Simplified for now, assuming success if reached here)
    # Error handling logic will be refined in future phases
    state = EventState.SUCCEEDED
    error_msg = None

    # TODO: Check if result_payload is an Exception wrapper
    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100]
            if state == EventState.SUCCEEDED
            else None,
        },
    }
~~~~~
~~~~~python.new
    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    # Heuristic: Extract task_name from physical name "Stain(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # Determine Status (Simplified for now, assuming success if reached here)
    # Error handling logic will be refined in future phases
    state = EventState.SUCCEEDED
    error_msg = None

    # TODO: Check if result_payload is an Exception wrapper
    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": task_name,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100]
            if state == EventState.SUCCEEDED
            else None,
        },
    }
~~~~~

#### Acts 4: 创建 VM 遥测 E2E 测试

创建一个集成测试，使用 `Engine` 和 `VMExecutionStrategy` 运行一个工作流，并断言 `EventBus` 收到了包含正确元数据的 `TaskExecutionFinished` 事件。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_telemetry.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime import Engine, EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.testing import SpySubscriber


@pytest.mark.asyncio
async def test_vm_telemetry_e2e():
    """
    Verifies that running a workflow with the VM strategy produces
    correct telemetry events (Started/Finished) with populated
    task_name and run_id.
    """
    
    # 1. Define Workflow
    @cs.task(name="MyCalcTask")
    def calc(x: int) -> int:
        return x * 2

    # Using a condition to ensure the new VM traversal logic is also exercised
    @cs.task(name="MyCondition")
    def should_run() -> bool:
        return True

    workflow = calc(21).run_if(should_run())

    # 2. Setup Engine with VM
    bus = EventBus()
    spy = SpySubscriber(bus)
    
    engine = Engine(
        solver=NativeSolver(), 
        executor=LocalExecutor(), 
        bus=bus
    )

    # 3. Run
    # Force use_vm=True to test the VM strategy
    result = await engine.run(workflow, use_vm=True)
    assert result == 42

    # 4. Assert Telemetry
    
    # A. Check Start Events
    started = spy.events_of_type(TaskExecutionStarted)
    task_names = sorted([e.task_name for e in started])
    # Note: 'calc' node and 'should_run' node.
    # The names come from @cs.task(name=...).
    assert "MyCalcTask" in task_names
    assert "MyCondition" in task_names
    
    # Check Run ID presence
    run_id = started[0].run_id
    assert run_id is not None
    assert all(e.run_id == run_id for e in started)

    # B. Check Finish Events
    finished = spy.events_of_type(TaskExecutionFinished)
    finished_map = {e.task_name: e for e in finished}
    
    assert "MyCalcTask" in finished_map
    calc_event = finished_map["MyCalcTask"]
    
    assert calc_event.status == "Succeeded"
    assert calc_event.duration >= 0.0
    assert calc_event.run_id == run_id
    
    print("VM Telemetry E2E Passed: Context and Metadata verified.")
~~~~~

### 下一步建议
运行 `test_vm_telemetry.py`。如果通过，说明我们的 VM 策略已经具备了正确的代码发现能力和完整的遥测能力，这标志着 Cascade 3.0 的物理内核已经稳定可用。
