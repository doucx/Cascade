Of course. Following our development process, we will now create a comprehensive test suite for the `cs-controller`'s `pause` command.

This plan involves two key actions: first, a minor refactoring of the `cs-controller`'s code to improve testability, and second, the creation of the test file itself. The refactoring will extract the core asynchronous logic from the `typer` command function into a standalone, easily callable function, allowing us to test the logic directly without needing the `typer` test runner.

## [WIP] test: Create integration tests for cs-controller publish logic

### 用户需求
为 `cs-controller` 的 `pause` 命令创建一套集成测试，以验证其能否正确地连接到 MQTT Broker 并发布符合规范的约束指令。

### 评论
这是确保 `cs-controller` 可靠性的关键一步。通过将核心发布逻辑提取到一个独立的函数中，我们能够编写出更清晰、更集中的单元/集成测试。这些测试将严格遵循 Mock 意图的原则，断言 `MqttConnector` 的 `publish` 方法是否被以正确的**主题**和**负载**调用，从而验证了其核心业务逻辑，而无需进行实际的网络通信。

### 目標
1.  重构 `packages/cascade-cli-controller/src/cascade/cli/controller/app.py`，将核心的异步逻辑提取到一个独立的、可测试的函数中。
2.  创建新的测试文件 `tests/cli-controller/test_app.py`。
3.  实现 `pytest` fixtures 来 Mock `MqttConnector` 和 `MessageBus`。
4.  编写测试用例，验证在不同 `scope` 参数下，是否能生成正确的主题和 `GlobalConstraint` payload。
5.  验证 `MessageBus` 是否被调用以提供正确的用户反馈。

### 基本原理
我们将 `typer` 命令函数 (`pause`) 的职责缩小为仅负责解析 CLI 参数和调用一个独立的业务逻辑函数（例如 `_publish_pause`)。这样一来，我们的测试就可以完全绕过 `typer` 的复杂性，直接 `await` 这个业务逻辑函数。测试将使用 `monkeypatch` 注入 Mock 版本的 `MqttConnector` 和 `bus`，然后断言这些 Mock 对象的方法是否被以预期的方式调用，从而验证了 `pause` 命令的正确意图。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/cli #concept/control-loop #scope/dx #ai/instruct #task/domain/cli #task/object/controller-tool #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `app.py` 以提高可测试性

我们首先将 `pause` 命令中的 `asyncio` 循环提取到一个独立的、可测试的 `async` 函数 `_publish_pause` 中。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """

    async def main_loop():
        connector = MqttConnector(hostname=hostname, port=port)
        try:
            bus.info("controller.connecting", hostname=hostname, port=port)
            await connector.connect()
            bus.info("controller.connected")

            # Create a unique, descriptive ID for the constraint
            constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id, scope=scope, type="pause", params={}
            )

            # Convert to dictionary for JSON serialization
            payload = asdict(constraint)

            # Publish to a structured topic based on scope
            topic = f"cascade/constraints/{scope.replace(':', '/')}"

            bus.info("controller.publishing", scope=scope, topic=topic)
            # The connector's publish is fire-and-forget
            await connector.publish(topic, payload)

            # In a real fire-and-forget, we can't be sure it succeeded,
            # but for UX we assume it did if no exception was raised.
            # Give a brief moment for the task to be sent.
            await asyncio.sleep(0.1)
            bus.info("controller.publish_success")

        except Exception as e:
            bus.error("controller.error", error=e)
        finally:
            await connector.disconnect()

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~python
async def _publish_pause(scope: str, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id, scope=scope, type="pause", params={}
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        # The connector's publish is fire-and-forget
        await connector.publish(topic, payload)

        # In a real fire-and-forget, we can't be sure it succeeded,
        # but for UX we assume it did if no exception was raised.
        # Give a brief moment for the task to be sent.
        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """
    try:
        asyncio.run(_publish_pause(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~

#### Acts 2: 创建 Controller 的测试文件

现在，我们可以为这个新的、独立的 `_publish_pause` 函数编写干净的测试。

~~~~~act
write_file
tests/cli-controller/test_app.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock, AsyncMock, ANY

# The module we are testing
from cascade.cli.controller import app as controller_app


@pytest.fixture
def mock_messaging_bus(monkeypatch) -> MagicMock:
    """Mocks the global message bus used by the controller app."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.cli.controller.app.bus", mock_bus)
    return mock_bus


@pytest.fixture
def mock_connector(monkeypatch) -> AsyncMock:
    """Mocks the MqttConnector class to prevent network calls."""
    mock_instance = AsyncMock()
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cascade.cli.controller.app.MqttConnector", mock_class)
    return mock_instance


@pytest.mark.asyncio
async def test_publish_pause_global_scope(mock_messaging_bus, mock_connector):
    """
    Verify publishing a pause command for the 'global' scope.
    """
    # Act: Call the core logic function
    await controller_app._publish_pause(
        scope="global", hostname="mqtt.test", port=1234
    )

    # Assert Connector Lifecycle
    mock_connector.connect.assert_awaited_once()
    mock_connector.publish.assert_awaited_once()
    mock_connector.disconnect.assert_awaited_once()

    # Assert Publish Intent
    # 1. Capture the arguments passed to publish
    call_args = mock_connector.publish.call_args
    topic = call_args.args[0]
    payload = call_args.args[1]

    # 2. Verify the topic and payload
    assert topic == "cascade/constraints/global"
    assert payload["scope"] == "global"
    assert payload["type"] == "pause"
    assert "id" in payload  # Check for presence of generated ID

    # Assert User Feedback
    mock_messaging_bus.info.assert_any_call(
        "controller.publishing", scope="global", topic="cascade/constraints/global"
    )
    mock_messaging_bus.info.assert_any_call("controller.publish_success")


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
    topic = call_args.args[0]
    payload = call_args.args[1]

    # Verify that the ':' was correctly replaced with '/' for the topic
    assert topic == "cascade/constraints/task/api_call"
    assert payload["scope"] == "task:api_call"
    assert payload["type"] == "pause"
~~~~~
