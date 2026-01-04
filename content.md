简要回答
测试失败是因为 `EventBus` 已经按预期工作，将底层的 `EventIR` 字典转换为了高级的 **Rich Event Objects** (如 `TaskExecutionStarted`)，而我们的测试代码仍试图将其作为原始字典或具有 `type` 属性的对象来访问。

这实际上是一个好消息：错误信息中的 `run_id='a22e49a7...'` 证明了上下文注入机制**已经生效**。我们需要做的仅仅是修复测试代码，使其针对 Rich Event 对象进行断言。

## [WIP] test(vm): 修复 Trace 上下文注入测试的断言逻辑

### 用户需求
修复 `packages/cascade-vm/tests/integration/test_context_injection.py` 中的 `AttributeError`。
1.  修改测试以导入并使用 `cascade.runtime.events` 中的 `TaskExecutionStarted` 和 `TaskExecutionFinished` 类。
2.  更新 `wait_for_event` 的谓词逻辑，使用 `isinstance` 检查类型，并检查 `task_id` 和 `status`。
3.  更新后续的断言逻辑，直接验证 Rich Event 对象的 `run_id` 属性。

### 评论
这个修复确认了我们的架构分层（VM -> IR -> EventBus -> Rich Events）正在协同工作。直接验证 Rich Event 不仅修复了测试，还隐式验证了从 IR 到 Rich Event 的转换逻辑是否正确保留了上下文信息。

### 目标
让集成测试通过。

### 基本原理
测试应反映系统的实际行为。系统现在的行为是发出领域对象，而不是原始数据，因此测试必须演进以匹配这一契约。

### 标签
#intent/test #intent/fix #flow/ready #priority/high #comp/vm #task/domain/observability #task/object/context-injection #task/action/verification #task/state/end

---

### Script

#### Acts 1: 修复测试断言

我们将修改测试文件，导入正确的事件类，并调整断言逻辑。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python.old
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, Token
from cascade.spec.triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec import EventType
from cascade.vm.harness import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
~~~~~
~~~~~python.new
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, Token
from cascade.spec.triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from cascade.spec.ports import PortDef, PortRole
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.vm.harness import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python.old
        # 4. Wait for completion (Stainer success event)
        # We look for the SUCCEEDED event from the stainer
        def is_success(e):
            return (
                e.type == EventType.LIFECYCLE 
                and e.payload["data"]["state"] == "succeeded"
                and e.payload["phy"]["nid"] == "task.stain"
            )
        
        await runner.wait_for_event(is_success, timeout=2.0)

        # 5. Verify Events
        events = runner._captured_events
        
        # Filter relevant lifecycle events
        lifecycle_events = [e for e in events if e.type == EventType.LIFECYCLE]
        assert len(lifecycle_events) >= 2  # At least Bleacher(Running) and Stainer(Succeeded)

        for event in lifecycle_events:
            # THE CORE ASSERTION:
            # Every lifecycle event must carry the correct run_id in its context
            assert "ctx" in event.payload, f"Event {event} missing ctx"
            assert event.payload["ctx"].get("rid") == runner.run_id, \
                f"Run ID mismatch in event {event.payload['phy']['nid']}"

        print("Context propagation verified successfully.")
~~~~~
~~~~~python.new
        # 4. Wait for completion (Stainer success event)
        # We look for the SUCCEEDED event from the stainer (which maps to TaskExecutionFinished)
        # Note: standard_stainer emits an IR with logic_id derived from node id.
        # "task.stain" -> logical_id "task"
        def is_success(e):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == "task"
                and e.status == "Succeeded"
            )
        
        await runner.wait_for_event(is_success, timeout=2.0)

        # 5. Verify Events
        events = runner._captured_events
        
        # Filter relevant lifecycle events (Rich Objects)
        lifecycle_events = [
            e for e in events 
            if isinstance(e, (TaskExecutionStarted, TaskExecutionFinished))
        ]
        assert len(lifecycle_events) >= 2  # At least Started and Finished

        for event in lifecycle_events:
            # THE CORE ASSERTION:
            # Every lifecycle event object must carry the correct run_id
            # The translation layer (Event.from_ir) extracts 'ctx.rid' -> 'event.run_id'
            assert event.run_id == runner.run_id, \
                f"Run ID mismatch in event {event}"

        print("Context propagation verified successfully.")
~~~~~

### 下一步建议

再次运行测试。一旦通过，Phase 4 上下文注入部分即告完成。

接下来我们可以进入 **Phase 5: 清理与验证 (Cleanup & Verification)**，清理旧的 Hack 代码并进行 E2E 验证。
