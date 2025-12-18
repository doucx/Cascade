import pytest
from unittest.mock import AsyncMock
from cascade.connectors.mqtt import MqttConnector

@pytest.fixture(autouse=True)
def check_aiomqtt_installed():
    try:
        import aiomqtt
    except ImportError:
        pytest.skip("aiomqtt not installed, skipping MQTT connector tests.")

def test_mqtt_connector_instantiation():
    """
    Tests that the MqttConnector can be instantiated.
    """
    connector = MqttConnector(hostname="localhost", port=1234)
    assert connector.hostname == "localhost"
    assert connector.port == 1234

@pytest.mark.asyncio
async def test_connect_and_disconnect_lifecycle(mocker):
    """
    Tests that connect() creates and connects a client, and disconnect() disconnects it.
    """
    # 1. Mock the aiomqtt.Client class
    mock_client_instance = AsyncMock()
    mock_client_class = mocker.patch("cascade.connectors.mqtt.connector.aiomqtt.Client")
    mock_client_class.return_value = mock_client_instance

    # 2. Setup connector
    connector = MqttConnector(hostname="test.broker", port=9999, client_id="tester")

    # 3. Test connect()
    await connector.connect()

    # Assert that the client was instantiated with correct parameters
    mock_client_class.assert_called_once_with(
        hostname="test.broker", port=9999, client_id="tester"
    )

    # Assert that the client's connect method was awaited
    mock_client_instance.connect.assert_awaited_once()

    # 4. Test disconnect()
    await connector.disconnect()

    # Assert that the client's disconnect method was awaited
    mock_client_instance.disconnect.assert_awaited_once()