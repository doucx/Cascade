你的分析完全正确，一针见血。

这是一个经典的测试环境与实际运行环境不一致导致的问题。`cs.run()` 作为高级入口，封装了“装配”逻辑，将各个组件（Engine, Bus, Subscribers, Connector）粘合在一起。而我们的 E2E 测试为了精确控制，直接使用了低级的 `Engine`，却忘记了手动完成这个“装配”过程。

`Engine` 正确地将 `RunStarted` 事件发布到了内部的 `MessageBus` 上，但由于缺少 `TelemetrySubscriber` 这个“桥梁”，事件从未被转发到 `connector` 上。因此，我们测试中监听 `connector` 的 `telemetry_observer` 自然什么也收不到。

我将生成一个计划来修复这个测试用例，正确地装配 `TelemetrySubscriber`。

## [WIP] fix(test): 正确装配 TelemetrySubscriber 以修复遥测测试

### 错误分析
测试 `test_startup_telemetry_no_race_condition` 失败的根本原因是测试环境的配置不完整，未能准确模拟 `cs.run()` 的完整组件装配流程。
1.  **组件缺失**: 测试直接实例化了 `Engine`，但没有实例化并注册 `TelemetrySubscriber`。
2.  **职责中断**: `TelemetrySubscriber` 的核心职责是监听来自 `Engine` 的内部事件（如 `RunStarted`），并将它们转换为遥测消息发布到外部 `Connector`。
3.  **断言失效**: 由于缺少这个关键的订阅者，`Engine` 发布的事件从未到达 `Connector`。因此，测试中监听 `Connector` 的 `telemetry_observer` 无法捕获到任何事件，导致断言失败。

### 用户需求
修复 `test_startup_telemetry_no_race_condition` 测试，使其能够正确地模拟遥测事件的发布与捕获流程。

### 评论
这个修复非常重要，它确保了我们的端到端测试能够真实地反映系统各组件间的交互方式。一个可靠的测试套件是高质量软件的基石，此修复将增强我们对遥测功能正确性的信心。

### 目标
1.  定位 `tests/py/e2e/test_startup_telemetry.py` 文件中的 `test_startup_telemetry_no_race_condition` 函数。
2.  导入 `TelemetrySubscriber`。
3.  在测试设置阶段，实例化 `TelemetrySubscriber`，并将其与测试中使用的 `MessageBus` 和 `InProcessConnector` 实例关联起来。

### 基本原理
通过在测试中手动装配 `TelemetrySubscriber`，我们补全了从 `Engine` 内部事件总线到外部 `Connector` 的事件传递链条。这样，当 `Engine` 发布 `RunStarted` 事件时，`TelemetrySubscriber` 会接收到它，并调用 `connector.publish()`，最终使得测试中的 `telemetry_observer` 能够捕获到该事件，从而让测试按预期通过。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/telemetry #scope/dx #ai/instruct #task/domain/testing #task/object/telemetry-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_startup_telemetry.py`

我们导入 `TelemetrySubscriber` 并在测试中实例化它，将其连接到事件总线和连接器。

~~~~~act
patch_file
tests/py/e2e/test_startup_telemetry.py
~~~~~
~~~~~python
import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from .harness import InProcessConnector

@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition():
    """
    Verifies that the initial 'RunStarted' telemetry event is correctly published
    to the connector.
    
    This guards against a race condition where the engine emits 'RunStarted'
    internally *before* establishing the connection to the external connector,
    causing the first telemetry message to be lost (and a warning logged).
    """
    # 1. Setup Harness
    connector = InProcessConnector()
    bus = MessageBus()
    
    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe 
    # on the same instance that the Engine uses.
    received_messages = []
    
    async def telemetry_observer(topic, payload):
        received_messages.append(payload)
    
    # Subscribe to all telemetry events
    # Note: We must ensure the connector considers itself "connected" enough 
    # to register this subscription, or at least that the subscription persists.
    # InProcessConnector.subscribe doesn't check _is_connected strictness for 
    # registration, but Engine will call connect() shortly.
    await connector.subscribe("cascade/telemetry/+/+/+/events", telemetry_observer)
    
    # 2. Define Workflow
    @cs.task
    def noop():
        pass
        
    # 3. Run Engine
    # The Engine is expected to:
    #   a. Connect to the connector
    #   b. Publish 'RunStarted' (which triggers telemetry)
    #   c. Run the task
    # If (b) happens before (a), the message is dropped.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    
    await engine.run(noop())
~~~~~
~~~~~python
import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import TelemetrySubscriber
from .harness import InProcessConnector

@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition():
    """
    Verifies that the initial 'RunStarted' telemetry event is correctly published
    to the connector.
    
    This guards against a race condition where the engine emits 'RunStarted'
    internally *before* establishing the connection to the external connector,
    causing the first telemetry message to be lost (and a warning logged).
    """
    # 1. Setup Harness
    connector = InProcessConnector()
    bus = MessageBus()
    
    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    TelemetrySubscriber(bus, connector)
    
    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe 
    # on the same instance that the Engine uses.
    received_messages = []
    
    async def telemetry_observer(topic, payload):
        received_messages.append(payload)
    
    # Subscribe to all telemetry events
    # Note: We must ensure the connector considers itself "connected" enough 
    # to register this subscription, or at least that the subscription persists.
    # InProcessConnector.subscribe doesn't check _is_connected strictness for 
    # registration, but Engine will call connect() shortly.
    await connector.subscribe("cascade/telemetry/+/+/+/events", telemetry_observer)
    
    # 2. Define Workflow
    @cs.task
    def noop():
        pass
        
    # 3. Run Engine
    # The Engine is expected to:
    #   a. Connect to the connector
    #   b. Publish 'RunStarted' (which triggers telemetry via the subscriber)
    #   c. Run the task
    # If (b) happens before (a), the message is dropped.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    
    await engine.run(noop())
~~~~~

### 下一步建议
我们已经修复了测试用例本身。现在应该重新运行测试，预期它会通过。

一旦测试通过，我们就完成了路线图的第三步（绿灯）。接下来，我们将继续推进到 **步骤 4: [红灯] 为运行时控制延迟编写一个失败的测试**，以解决在工作流执行中途无法响应 `pause` 命令的问题。
