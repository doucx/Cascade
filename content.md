简要回答
你遇到的错误有两个根本原因：
1.  **VM 遥测缺失 `run_id`**: `VMExecutionStrategy` 在启动 Reactor 时，没有将 `run_id` 作为“创世微量 (Genesis Trace)”注入到初始令牌中。导致物理层生成的事件缺失了上下文信息。
2.  **Mock 属性缺失**: 在 `cascade-std` 的单元测试中，`standard_bleacher` 和 `standard_stainer` 试图访问 `node.name` 来推断任务名，但测试用的 Mock 对象没有设置该属性，导致 `AttributeError`。

我将修复这两个问题。

## [WIP] fix(vm): 修复 VM 策略中的 run_id 注入缺失及 Std 库测试的 Mock 属性问题

### 用户需求
1.  修复 `test_vm_telemetry.py` 中 `run_id` 为 None 的断言失败。
2.  修复 `cascade-std` 单元测试中因 Mock 对象缺失 `name` 属性导致的 `AttributeError`。

### 评论
这是一个典型的“集成细节”与“测试保真度”问题。
*   在运行时层面，我们确立了“创世注入”模式，即 `run_id` 必须在 Reactor 启动瞬间注入，而不是作为全局变量。之前的代码遗漏了这一步。
*   在测试层面，Mock 对象必须如实反映它所模拟的真实对象的契约。`PhysicsNode` 有 `name` 属性，代码依赖它，因此 Mock 必须提供它。

### 目标
1.  修改 `VMExecutionStrategy.execute`，在调用 `reactor.prime()` 时传入包含 `rid` 的 `genesis_trace`。
2.  修改 `test_bleacher.py` 和 `test_stainer.py` 中的 Mock 创建辅助函数，显式设置 `node.name`。

### 基本原理
1.  **创世注入**: `Reactor.prime(genesis_trace=...)` 是将环境上下文（如 `run_id`）物理化为 Token Trace 的唯一合法入口。这确保了所有从源头产生的 Token 都携带了正确的上下文。
2.  **Mock 完整性**: `standard_bleacher` 使用启发式逻辑（检查 `node.name`）来提取逻辑任务名。测试必须满足这一前置条件才能验证核心逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/observability #concept/state

---

### Script

#### Acts 1: 修复 VM 策略中的创世注入

我们将更新 `VMExecutionStrategy`，使其将 `ExecutionContext` 中的 `run_id` 注入到 Reactor 中。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Prime the reactor (fill constants, pulses)
        reactor.prime()

        # Result Future
~~~~~
~~~~~python.new
        # Prime the reactor (fill constants, pulses)
        # Genesis Injection: Inject the run_id into the initial static tokens
        reactor.prime(genesis_trace={"rid": context.run_id})

        # Result Future
~~~~~

#### Acts 2: 修复 cascade-std 单元测试中的 Mock 设置

我们将更新测试辅助函数，为 Mock 节点设置 `name` 属性，使其能够通过被测代码中的 `startswith` 检查。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.id = "test_node.bleach"  # Required for ID extraction logic
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node
~~~~~
~~~~~python.new
def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.id = "test_node.bleach"  # Required for ID extraction logic
    node.name = "Bleach(test_node)"  # Fix: Set name for heuristic check
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.id = "mock.stain.node"  # Add the missing ID attribute
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node
~~~~~
~~~~~python.new
def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.id = "mock.stain.node"  # Add the missing ID attribute
    node.name = "Stain(mock_task)"  # Fix: Set name for heuristic check
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node
~~~~~

### 下一步建议
修复后，建议重新运行 `test_vm_telemetry.py` 和 `cascade-std` 的单元测试以确认通过。如果一切顺利，我们就可以确信 VM 运行时的基本可观测性链路已经打通，并且标准库组件逻辑正确。接下来可以关注更高级的特性或性能优化。
