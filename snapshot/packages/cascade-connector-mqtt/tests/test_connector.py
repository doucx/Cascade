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
async def test_subscribe_receives_messages(mock_client):
    """
    Tests that the connector starts a listener loop, and when messages arrive,
    the registered callback is invoked with decoded data.
    """
    connector = MqttConnector(hostname="test.broker")

    # 1. Setup Mock Message Stream
    # Create a simple AsyncIterator to simulate client.messages
    incoming_payload = {"command": "pause"}
    incoming_topic = "control/pause"
    
    class MockMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    async def message_stream():
        # Yield one message then sleep forever to simulate an open but idle connection
        # (This prevents the loop from exiting immediately and closing the mock)
        yield MockMessage(incoming_topic, json.dumps(incoming_payload).encode("utf-8"))
        await asyncio.sleep(10) # Simulate idle waiting

    # Mock the 'messages' property of the client
    mock_client.messages = message_stream()

    await connector.connect()

    # 2. Register a callback
    received_events = []
    async def my_callback(topic, data):
        received_events.append((topic, data))

    await connector.subscribe(incoming_topic, my_callback)

    # 3. Verify subscription was sent to broker
    mock_client.subscribe.assert_awaited_with(incoming_topic)

    # 4. Wait for the loop to process the message
    # We yield control a few times to ensure the background task runs
    await asyncio.sleep(0.01)

    # 5. Assert callback invocation
    assert len(received_events) == 1
    assert received_events[0][0] == incoming_topic
    assert received_events[0][1] == incoming_payload

    # Cleanup
    await connector.disconnect()