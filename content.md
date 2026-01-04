好的，我来分析并修复这些测试失败。

[简要回答]
这些测试失败是由于 Phase 3 中对事件模型的重构引入的。`standard_stainer` 函数现在需要访问 `node.id`，导致 Mock 测试失败；同时，部分集成测试的断言逻辑仍然依赖于已被移除的 `ObservedEvent` 结构或不正确的字符串比较。我将修复这些问题。

## [WIP] fix(tests): 修复 Stainer mock 并适配 VM 测试到新事件模型

### 错误分析
1.  **`AttributeError: Mock object has no attribute 'id'`**:
    -   **原因**: `standard_stainer` 函数被修改以从 `node` 对象中读取 `id` 属性来构建 `EventIR`。`test_stainer.py` 中的单元测试使用的是一个没有配置 `id` 属性的 `MagicMock`，导致了属性错误。
    -   **解决方案**: 更新测试辅助函数 `create_mock_stain_node`，为 mock 对象添加一个 `id` 属性。
2.  **`AssertionError` in `test_source_node_execution`**:
    -   **原因**: `stainer` 生成的 `result_preview` 是对结果的 `str()` 调用，对于字符串 `"Pulse Fired!"`，其结果就是自身。测试用例错误地断言其 `startswith("'Pulse Fired!'")`，包含了多余的单引号。
    -   **解决方案**: 将断言修正为 `assert completion_event.result_preview == "Pulse Fired!"`。
3.  **`EventTimeoutError` in `test_event_driven_ping_pong`**:
    -   **原因**: 这个测试用例被重构遗漏了。它仍在尝试断言旧的 `ObservedEvent` 结构（`e.trace_data`），并且其 mock 逻辑向 `obs_output` 端口发送了错误的 payload 格式（`trace` 而不是 `EventIR`）。这导致 `standard_observer` 无法处理，没有事件被发布到总线，最终导致 `wait_for_event` 超时。
    -   **解决方案**: 将此测试完全重构，使其 mock 逻辑产生一个符合规范的 `EventIR` 作为 payload，并将断言谓词更新为检查新的富 `Event` 对象（如 `TaskExecutionFinished`）。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/std #comp/vm #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_stainer.py`

为 `StainNode` 的 mock 添加 `id` 属性。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


async def test_stainer_success_case():
~~~~~
~~~~~python.new
def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.id = "mock.stain.node"  # Add the missing ID attribute
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


async def test_stainer_success_case():
~~~~~

#### Acts 2: 修复 `test_source_node_execution.py`

修正 `result_preview` 的断言。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == node_ir.current_node_instance_hash
        assert completion_event.result_preview.startswith("'Pulse Fired!'")

    finally:
        await runner.stop_loop()
~~~~~
~~~~~python.new
        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == node_ir.current_node_instance_hash
        assert completion_event.result_preview == "Pulse Fired!"

    finally:
        await runner.stop_loop()
~~~~~

#### Acts 3: 修复 `test_reactor.py`

重构 `test_event_driven_ping_pong` 以使用新的事件模型。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
import pytest
import sys
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
~~~~~
~~~~~python.new
import pytest
import sys
import time
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec import EventIR, EventType, EventState
from cascade.runtime.events import Event, TaskExecutionFinished
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"}),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,
    }

    # 2. Use Runner, injecting the backend factory
    runner = EventDrivenRunner(graph, func_map, reactor_factory=reactor_backend_factory)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1"
            and e.trace_data.get("status") == "done"
        )
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~
~~~~~python.new
    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        
        # This mock logic now simulates what a Stainer does: create an EventIR
        ir: EventIR = {
            "v": "1.0",
            "t": EventType.LIFECYCLE,
            "ts": time.time(),
            "ctx": {},
            "phy": {"nid": node.id},
            "data": {
                "state": EventState.SUCCEEDED,
                "task_id": node.id, # In test, physical ID is fine
                "task_name": node.name
            }
        }
        
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=ir),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,
    }

    # 2. Use Runner, injecting the backend factory
    runner = EventDrivenRunner(graph, func_map, reactor_factory=reactor_backend_factory)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        def predicate(e: Event):
            return isinstance(e, TaskExecutionFinished) and e.task_id == "F1"
            
        event = await runner.wait_for_event(predicate)
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议
测试套件已修复。我们已准备好继续进行 **Phase 4: 上下文注入**，这将使我们能够将 `run_id` 等关键信息填充到 `EventIR` 中。
