# [WIP] fix: 修复遥测订阅者的异步调用问题及控制器测试

## 摘要

本计划旨在修复导致遥测数据无法发送的严重 Bug，并修正因 API 变更导致的测试失败。核心修复是将 `TelemetrySubscriber.on_event` 从异步方法改为同步包装器，以适配同步的 `MessageBus` 架构，确保异步的 MQTT 发布任务被正确调度。

## 错误分析

### 1. 遥测失效 (RuntimeWarning)
*   **现象**: 用户报告 `cs-observer` 没有任何输出，且终端出现 `RuntimeWarning: coroutine 'TelemetrySubscriber.on_event' was never awaited`。
*   **原因**: `MessageBus.publish` 是同步方法，它遍历并直接调用所有 handler。`TelemetrySubscriber.on_event` 被定义为 `async def`。在 Python 中，调用一个 `async` 函数不会执行其函数体，而是返回一个 coroutine 对象。由于 `MessageBus` 没有（也不能）`await` 这个对象，导致实际的遥测逻辑从未执行。
*   **解决方案**: 将 `on_event` 改为同步方法。在方法内部使用 `asyncio.create_task` 将实际的异步处理逻辑调度到事件循环中执行。这符合 Fire-and-Forget 的遥测设计原则。

### 2. 测试失败
*   **现象**: `tests/cli-controller/test_controller_app.py` 报错 `TypeError: _publish_pause() missing 1 required positional argument: 'ttl'`。
*   **原因**: 此前的重构为 `_publish_pause` 增加了 `ttl` 参数，但单元测试代码未同步更新。
*   **解决方案**: 更新测试用例中的函数调用签名。

### 3. 用户体验缺失
*   **现象**: 用户无法确认 Engine 是否成功连接到了 MQTT Broker。
*   **原因**: `Engine` 在建立连接时没有发出任何用户可见的日志消息。
*   **解决方案**: 在 `runtime_events.json` 中添加连接相关的消息 ID，并在 `Engine` 成功连接后触发该消息。

## 用户需求
1.  修复 `cs-observer` 无法接收数据的问题。
2.  修复 CLI Controller 的单元测试。
3.  在 Engine 启动时提供明确的 MQTT 连接状态反馈。

## 评论
这是一个关键的修复。当前的遥测系统实际上是断开的，这阻碍了 Phase 2 和 Phase 3 功能的验证。异步/同步边界的处理错误是 Python 异步编程中的常见陷阱，将其改为显式的 Task 调度是正确的做法。

## 目标
1.  重构 `TelemetrySubscriber` 以正确处理异步事件发布。
2.  在 `Engine` 启动流程中增加连接状态的反馈。
3.  修复所有破坏的测试用例。

## 基本原理
Cascade 的 `MessageBus` 被设计为核心业务逻辑的同步解耦层。强制它变成异步会产生连锁反应，影响所有同步的业务代码。因此，适配器（Subscriber）必须承担起“同步转异步”的桥梁职责。

## 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #comp/cli #concept/async #scope/core #ai/instruct #task/domain/telemetry #task/object/subscriber #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 `TelemetrySubscriber` 的异步调用问题

我们将修改 `TelemetrySubscriber`，使其 `on_event` 方法变为同步，并内部调度异步任务。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    def _create_header(self, run_id: str) -> dict:
        return {
            "v": "1.0",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "org_id": os.getenv("CASCADE_ORG_ID", "local"),
            "project_id": os.getenv("CASCADE_PROJECT_ID", "default"),
            "source": self._source_id,
        }

    async def on_event(self, event: Event):
        if not event.run_id:
            return

        payload = self._create_header(event.run_id)
        topic = f"cascade/telemetry/{payload['org_id']}/{payload['project_id']}/{event.run_id}/events"

        event_body = {}
        if isinstance(
            event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped)
        ):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if event.status == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, "duration", 0) * 1000,
                "error": getattr(event, "error", None) or "",
            }

        elif isinstance(event, RunStarted):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STARTED"}

        elif isinstance(event, RunFinished):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STOPPED"}

        # We can add more event types like ResourceEvent later

        if event_body:
            payload["body"] = event_body
            # Fire-and-forget publish
            asyncio.create_task(self._connector.publish(topic, payload))
~~~~~
~~~~~python
    def _create_header(self, run_id: str) -> dict:
        return {
            "v": "1.0",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "org_id": os.getenv("CASCADE_ORG_ID", "local"),
            "project_id": os.getenv("CASCADE_PROJECT_ID", "default"),
            "source": self._source_id,
        }

    def on_event(self, event: Event):
        """
        Handles incoming events synchronously and schedules asynchronous publishing.
        This bridges the synchronous MessageBus with the asynchronous Connector.
        """
        if not event.run_id:
            return

        # Prepare payload synchronously to avoid race conditions with event state
        payload = self._create_header(event.run_id)
        topic = f"cascade/telemetry/{payload['org_id']}/{payload['project_id']}/{event.run_id}/events"

        event_body = {}
        if isinstance(
            event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped)
        ):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", "") == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, "duration", 0) * 1000,
                "error": getattr(event, "error", None) or "",
            }

        elif isinstance(event, RunStarted):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STARTED"}

        elif isinstance(event, RunFinished):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STOPPED"}

        # If we have a valid body, schedule the publish task
        if event_body:
            payload["body"] = event_body
            asyncio.create_task(self._connector.publish(topic, payload))
~~~~~

#### Acts 2: 定义 Engine 连接相关的消息

在 `runtime_events.json` 中添加新的消息 ID。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
~~~~~
~~~~~json
    "task.retrying": "   - ⚠️ Task '{task_name}' failed, retrying (attempt {attempt}/{max_attempts}). Delaying for {delay:.2f}s. Error: {error}"
}
~~~~~
~~~~~json
    "task.retrying": "   - ⚠️ Task '{task_name}' failed, retrying (attempt {attempt}/{max_attempts}). Delaying for {delay:.2f}s. Error: {error}",

    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector."
}
~~~~~

#### Acts 3: 在 Engine 中添加连接反馈

修改 `Engine.run` 方法，在连接成功和断开时发出日志。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        try:
            if self.connector:
                await self.connector.connect()
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
                self.bus.info("engine.connector.connected")
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
~~~~~
~~~~~python
        finally:
            if self.connector:
                await self.connector.disconnect()
                self.bus.info("engine.connector.disconnected")
~~~~~

#### Acts 4: 修复 Controller 测试用例

更新测试代码以匹配新的 `_publish_pause` 签名。

~~~~~act
patch_file
tests/cli-controller/test_controller_app.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_publish_pause_global_scope(mock_messaging_bus, mock_connector):
    """
    Verify publishing a pause command for the 'global' scope.
    """
    # Act: Call the core logic function
    await controller_app._publish_pause(scope="global", hostname="mqtt.test", port=1234)

    # Assert Connector Lifecycle
    mock_connector.connect.assert_awaited_once()
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_publish_pause_global_scope(mock_messaging_bus, mock_connector):
    """
    Verify publishing a pause command for the 'global' scope.
    """
    # Act: Call the core logic function
    await controller_app._publish_pause(
        scope="global", ttl=None, hostname="mqtt.test", port=1234
    )

    # Assert Connector Lifecycle
    mock_connector.connect.assert_awaited_once()
~~~~~

~~~~~act
patch_file
tests/cli-controller/test_controller_app.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_publish_pause_specific_scope(mock_messaging_bus, mock_connector):
    """
    Verify that a scoped pause command generates the correct MQTT topic.
    """
    # Act
    await controller_app._publish_pause(
        scope="task:api_call", hostname="mqtt.test", port=1234
    )

    # Assert
    call_args = mock_connector.publish.call_args
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_publish_pause_specific_scope(mock_messaging_bus, mock_connector):
    """
    Verify that a scoped pause command generates the correct MQTT topic.
    """
    # Act
    await controller_app._publish_pause(
        scope="task:api_call", ttl=None, hostname="mqtt.test", port=1234
    )

    # Assert
    call_args = mock_connector.publish.call_args
~~~~~

### 下一步建议
应用此修复后，建议用户再次按照手动测试指南进行操作。特别是观察步骤 2，现在应该能在 Observer 中看到所有的任务状态事件，且在 Engine 终端中能看到 "📡 Engine connected to external connector." 的提示。
