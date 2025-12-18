import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from cascade.connectors.mqtt import MqttConnector

@pytest.fixture(autouse=True)
def check_aiomqtt_installed():
    try:
        import aiomqtt
    except ImportError:
        pytest.skip("aiomqtt not installed, skipping MQTT connector tests.")

@pytest.fixture
def mock_client(mocker):
    """Provides a mocked aiomqtt.Client instance and patches the class."""
    mock_instance = AsyncMock()
    # Configure the context manager protocol
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    
    mocker.patch("cascade.connectors.mqtt.connector.aiomqtt.Client", return_value=mock_instance)
    return mock_instance

def test_mqtt_connector_instantiation():
    """Tests that the MqttConnector can be instantiated."""
    connector = MqttConnector(hostname="localhost", port=1234)
    assert connector.hostname == "localhost"
    assert connector.port == 1234

@pytest.mark.asyncio
async def test_connect_and_disconnect_lifecycle(mock_client, mocker):
    """Tests that connect() creates and connects a client, and disconnect() disconnects it."""
    # 1. Setup connector
    connector = MqttConnector(hostname="test.broker", port=9999, client_id="tester")

    # 2. Test connect()
    await connector.connect()

    # Assert that the client was instantiated
    assert connector._client is mock_client
    # Assert that the client's connect method was awaited via context manager
    mock_client.__aenter__.assert_awaited_once()

    # 3. Test disconnect()
    await connector.disconnect()

    # Assert that the client's disconnect method was awaited via context manager
    mock_client.__aexit__.assert_awaited_once()
    assert connector._client is None

@pytest.mark.asyncio
async def test_publish_sends_json_and_is_fire_and_forget(mock_client):
    """
    Tests that publish() serializes the payload to JSON and sends it in a
    non-blocking manner.
    """
    connector = MqttConnector(hostname="test.broker")
    await connector.connect()

    topic = "telemetry/events"
    payload = {"run_id": "123", "status": "Succeeded"}

    # This should return immediately, creating a background task
    await connector.publish(topic, payload, qos=1)

    # Yield control to the event loop to allow the created task to run
    await asyncio.sleep(0)

    # Verify that the mock client's publish method was called with the correct args
    expected_json_payload = json.dumps(payload)
    mock_client.publish.assert_awaited_once_with(
        topic, payload=expected_json_payload, qos=1
    )

@pytest.mark.asyncio
async def test_publish_without_connect_does_nothing(mock_client):
    """
    Tests that calling publish() before connect() does not raise an error
    and does not try to publish anything (Fail-Silent Telemetry).
    """
    connector = MqttConnector(hostname="test.broker")
    
    # Do not call connect()
    
    await connector.publish("a/topic", {"data": 1})
    await asyncio.sleep(0)
    
    mock_client.publish.assert_not_called()

@pytest.mark.asyncio
async def test_subscribe_and_receive_message(mock_client, mocker):
    """
    Tests that subscribe() registers a callback that is correctly invoked
    when a message is received.
    """
    # 1. Setup a mock message and the async iterator for client.messages
    topic = "control/test"
    payload = {"command": "pause"}
    
    mock_message = mocker.MagicMock()
    mock_message.topic.value = topic
    mock_message.payload = json.dumps(payload).encode("utf-8")

    async def mock_message_iterator():
        yield mock_message

    mock_client.messages.__aiter__.return_value = mock_message_iterator()
    
    # 2. Setup connector and callback
    connector = MqttConnector(hostname="test.broker")
    callback = AsyncMock()
    
    # 3. Connect and Subscribe
    await connector.connect()
    await connector.subscribe(topic, callback)
    
    # Assert that the underlying client was told to subscribe
    mock_client.subscribe.assert_awaited_once_with(topic)
    
    # 4. Wait for the message handler loop to process the message
    # The loop is started by connect(), so a small sleep lets it run.
    await asyncio.sleep(0)
    
    # 5. Assert the callback was invoked with the correct, decoded arguments
    callback.assert_awaited_once_with(topic, payload)

    # 6. Disconnect should cancel the handler task
    with patch("asyncio.Task.cancel") as mock_cancel:
        # Re-fetch the task from the connector to patch it correctly
        handler_task = connector._handler_task
        if handler_task:
             mocker.patch.object(handler_task, 'cancel', wraps=handler_task.cancel)
             mock_cancel = handler_task.cancel

        await connector.disconnect()
        # Ensure the handler task created by connect() was cancelled
        if handler_task:
            assert mock_cancel.call_count == 1