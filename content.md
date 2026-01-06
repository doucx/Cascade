简要回答：
好的，我将修复 `test_event_driven_ping_pong` 测试失败的问题。

## [WIP] fix(vm): 修复 E2E 测试中的 Ref 解引用错误

### 错误分析

`test_event_driven_ping_pong` 失败是因为在 v3.1 架构中，物理层的数据载荷（Payload）强制为 `Ref` 对象，而测试用的 Mock 函数 `obs_enabled_logic` 试图直接对 `Ref` 对象执行整数加法 (`val + 1`)，导致 `TypeError`。

此外，由于测试未正确模拟 Ref 的解引用和再封装过程，且 `EventDrivenRunner` 未将 `ObjectStore` 暴露给 Reactor 内运行的函数，导致 Mock 函数无法通过合法途径获取数据。

### 用户需求

1.  修复 `EventDrivenRunner`，使其将 `ObjectStore` 注册到 `ResourceRegistry`，以便测试函数可以访问。
2.  更新 `test_reactor.py` 中的 Mock 逻辑，使其遵循 Ref-Based 协议：`Get Ref` -> `Dereference` -> `Compute` -> `Put Result` -> `Return Ref`。
3.  更新测试断言，以验证最终结果是否为指向正确值的 `Ref`。

### 评论

这是一个非常典型的架构升级带来的“阵痛”。它暴露了我们的测试代码（模拟器）落后于核心架构规范的问题。修复这个问题不仅能通过测试，还能进一步验证 Ref-Based 机制在 Reactor 内部的闭环流转。

### 目标

1.  修改 `packages/cascade-vm/src/cascade/vm/harness.py`，注册 `system.object_store`。
2.  修改 `packages/cascade-vm/tests/unit/test_reactor.py`，适配 Ref 操作。

### 基本原理

在 v3.1 中，Reactor 并不感知数据内容，只传递 `Ref`。任何试图操作数据的逻辑（即便是测试用的 Mock Worker）都必须显式地与 `ObjectStore` 交互。这增强了物理层的纯粹性。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/harness #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 EventDrivenRunner 中注册 ObjectStore

我们需要让运行在 Reactor 中的函数能够访问 `ObjectStore`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)

        # 4. Setup Reactor
~~~~~
~~~~~python.new
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
~~~~~

#### Acts 2: 修复 test_reactor.py 中的 Mock 逻辑和断言

我们将更新 `obs_enabled_logic` 以处理 `Ref`，并更新测试断言。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.object import Ref
from cascade.std.triad.observer import standard_observer
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
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
                "task_id": node.id,  # In test, physical ID is fine
                "task_name": node.name,
            },
        }

        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=ir),
        }
~~~~~
~~~~~python.new
    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        # Ref-Based Architecture Adaptation
        # 1. Get Store
        store = resources.get("system.object_store")
        
        # 2. Dereference Input
        ref_in = inputs["value"].payload
        assert isinstance(ref_in, Ref)
        val = store.get(ref_in)

        # 3. Compute
        new_val = val + 1
        
        # 4. Store Result
        ref_out = store.put(new_val)

        # This mock logic now simulates what a Stainer does: create an EventIR
        ir: EventIR = {
            "v": "1.0",
            "t": EventType.LIFECYCLE,
            "ts": time.time(),
            "ctx": {},
            "phy": {"nid": node.id},
            "data": {
                "state": EventState.SUCCEEDED,
                "task_id": node.id,  # In test, physical ID is fine
                "task_name": node.name,
            },
        }

        return {
            "result": Token(payload=ref_out),
            "obs_output": Token(payload=ir),
        }
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~
~~~~~python.new
        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        result_token = runner.memory.take("D2")
        
        # Verify it is a Ref and dereference it
        assert isinstance(result_token.payload, Ref)
        final_val = runner.object_store.get(result_token.payload)
        assert final_val == 11

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议

执行测试，确认 `test_reactor.py` 通过。
同时，可以再次运行 `test_context_injection.py` 确保它没有因为这次改动而受到负面影响（虽然不太可能，因为它是 E2E 测试，逻辑相对独立）。
