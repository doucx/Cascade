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