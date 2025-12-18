import pytest
from cascade.connectors.mqtt import MqttConnector

def test_mqtt_connector_instantiation():
    """
    Tests that the MqttConnector can be instantiated.
    """
    try:
        connector = MqttConnector(hostname="localhost")
        assert connector.hostname == "localhost"
    except ImportError:
        pytest.skip("aiomqtt not installed, skipping MQTT connector tests.")

# TODO: Add more tests for connect, disconnect, publish, and subscribe methods using a mock broker.