import pytest
from unittest.mock import MagicMock, AsyncMock

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
        scope="global", ttl=None, hostname="mqtt.test", port=1234
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
        scope="task:api_call", ttl=None, hostname="mqtt.test", port=1234
    )

    # Assert
    call_args = mock_connector.publish.call_args
    topic = call_args.args[0]
    payload = call_args.args[1]

    # Verify that the ':' was correctly replaced with '/' for the topic
    assert topic == "cascade/constraints/task/api_call"
    assert payload["scope"] == "task:api_call"
    assert payload["type"] == "pause"
