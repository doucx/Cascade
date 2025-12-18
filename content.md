# [WIP] fix: 修复 Engine 日志调用错误并增强测试稳定性

## 摘要

本计划旨在修复上一轮提交引入的 `AttributeError`，该错误导致了大量测试失败。同时，我们将引入新的运行时事件来规范化连接状态的反馈，并改进测试用例的稳定性。

## 错误分析

### 1. `AttributeError: 'MessageBus' object has no attribute 'info'`
*   **原因**: 在 `Engine.run` 方法中，我错误地在 `self.bus` 上调用了 `.info()` 方法。`self.bus` 是 `cascade.runtime.bus.MessageBus` 的实例（用于内部事件分发），而不是 `cascade.common.messaging.bus`（用于用户日志）。
*   **影响**: 导致 `Engine` 启动时崩溃，进而导致所有依赖 Engine 运行的测试（包括 E2E 测试和约束测试）全部失败。
*   **修复策略**: 遵循架构原则，`Engine` 不应直接打印日志。它应该发出 `Event`，由 `HumanReadableLogSubscriber` 负责将其转换为用户日志。我们将引入 `ConnectorConnected` 和 `ConnectorDisconnected` 事件。

### 2. `test_engine_updates_constraints_on_message` 失败
*   **原因**: 除了上述崩溃外，该测试依赖 `asyncio.sleep(0.01)` 来等待 Engine 订阅主题。这种基于时间的等待是脆弱的（Flaky），可能导致 Engine 尚未订阅时消息就已发出。
*   **修复策略**: 修改测试，使用轮询或 `asyncio.Event` 显式等待 `mock_connector.subscriptions` 被填充。

## 用户需求
1.  修复 CI 测试中的所有错误。
2.  确保 Engine 连接状态能正确反馈给用户。

## 评论
这是一个典型的“架构违规”导致的 Bug。混淆了 Event Bus 和 Message Bus 的职责。这次修复将纠正这一偏差，使架构更加清晰。

## 目标
1.  定义 `ConnectorConnected` 和 `ConnectorDisconnected` 事件。
2.  更新 `Engine` 以发布这些事件。
3.  更新 `HumanReadableLogSubscriber` 以处理这些事件并输出日志。
4.  增强测试用例的健壮性。

## 基本原理
通过事件解耦 Engine 和 日志系统，保持 Engine 的纯洁性。通过确定性等待消除测试中的竞争条件。

## 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/events #scope/core #ai/instruct #task/domain/telemetry #task/object/engine #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 定义连接器相关事件

在 `cascade.runtime.events` 中新增两个事件。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class ResourceReleased(ResourceEvent):
    """Fired when a resource is successfully torn down."""

    pass
~~~~~
~~~~~python
@dataclass(frozen=True)
class ResourceReleased(ResourceEvent):
    """Fired when a resource is successfully torn down."""

    pass


@dataclass(frozen=True)
class ConnectorConnected(Event):
    """Fired when the engine successfully connects to an external connector."""

    pass


@dataclass(frozen=True)
class ConnectorDisconnected(Event):
    """Fired when the engine disconnects from an external connector."""

    pass
~~~~~

#### Acts 2: 更新 `Engine` 以发布事件

将错误的 `self.bus.info()` 调用替换为 `self.bus.publish(ConnectorConnected(...))`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
~~~~~
~~~~~python
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        try:
            if self.connector:
                await self.connector.connect()
                self.bus.info("engine.connector.connected")
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            with ExitStack() as stack:
~~~~~
~~~~~python
        try:
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            with ExitStack() as stack:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        finally:
            if self.connector:
                await self.connector.disconnect()
                self.bus.info("engine.connector.disconnected")
~~~~~
~~~~~python
        finally:
            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))
~~~~~

#### Acts 3: 更新 `HumanReadableLogSubscriber` 处理日志

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    TaskRetrying,
    Event,
)
from cascade.interfaces.protocols import Connector
~~~~~
~~~~~python
    TaskRetrying,
    ConnectorConnected,
    ConnectorDisconnected,
    Event,
)
from cascade.interfaces.protocols import Connector
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
        event_bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        event_bus.subscribe(TaskSkipped, self.on_task_skipped)
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)

    def on_run_started(self, event: RunStarted):
~~~~~
~~~~~python
        event_bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        event_bus.subscribe(TaskSkipped, self.on_task_skipped)
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)
        event_bus.subscribe(ConnectorConnected, self.on_connector_connected)
        event_bus.subscribe(ConnectorDisconnected, self.on_connector_disconnected)

    def on_run_started(self, event: RunStarted):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )


class TelemetrySubscriber:
~~~~~
~~~~~python
    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )

    def on_connector_connected(self, event: ConnectorConnected):
        bus.info("engine.connector.connected")

    def on_connector_disconnected(self, event: ConnectorDisconnected):
        bus.info("engine.connector.disconnected")


class TelemetrySubscriber:
~~~~~

#### Acts 4: 修复测试中的时序竞争

修改 `test_engine_constraints.py` 中的 `test_engine_updates_constraints_on_message`，使用轮询等待订阅生效。

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Give the engine a moment to start and subscribe
    await asyncio.sleep(0.01)

    # Simulate receiving a constraint message
    constraint_payload = {
~~~~~
~~~~~python
    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Simulate receiving a constraint message
    constraint_payload = {
~~~~~

同样修复 `test_engine_handles_malformed_constraint_payload`。

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    @task
    def dummy_task():
        pass

    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))
    await asyncio.sleep(0.01)

    # Payload missing the required 'id' key
    malformed_payload = {
~~~~~
~~~~~python
    @task
    def dummy_task():
        pass

    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))
    
    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Payload missing the required 'id' key
    malformed_payload = {
~~~~~

### 下一步建议
运行测试以确认所有问题已解决。一旦通过，即可进行 Git 提交。
