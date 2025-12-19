import pytest
import asyncio
from cascade.connectors.local import LocalBusConnector

@pytest.fixture
async def local_bus():
    """Provides a fresh LocalBus environment for each test."""
    # LocalBusConnector uses shared class state, so we must clear it before each test
    LocalBusConnector._reset_broker_state()
    yield
    LocalBusConnector._reset_broker_state()

@pytest.mark.asyncio
async def test_bus_connectivity_between_instances(local_bus):
    """Test that two separate instances share the same 'bus'."""
    pub_connector = LocalBusConnector()
    sub_connector = LocalBusConnector()
    await pub_connector.connect()
    await sub_connector.connect()

    received = []
    async def callback(topic, payload):
        received.append(payload)

    await sub_connector.subscribe("chat/room1", callback)
    
    # Publish from the other connector
    payload = {"msg": "hello"}
    await pub_connector.publish("chat/room1", payload)
    
    # Allow loop to process
    await asyncio.sleep(0.01)
    
    assert len(received) == 1
    assert received[0] == payload

    await pub_connector.disconnect()
    await sub_connector.disconnect()

@pytest.mark.asyncio
async def test_retained_messages(local_bus):
    """Test that retained messages are delivered to new subscribers immediately."""
    pub_connector = LocalBusConnector()
    await pub_connector.connect()

    # 1. Publish a retained message
    status = {"status": "online"}
    await pub_connector.publish("device/1/status", status, retain=True)

    # 2. Subscribe AFTER publishing
    sub_connector = LocalBusConnector()
    await sub_connector.connect()
    
    received = []
    async def callback(topic, payload):
        received.append((topic, payload))

    # This should trigger immediate delivery of the retained message
    await sub_connector.subscribe("device/+/status", callback)
    
    # Retained messages are delivered synchronously in our implementation, 
    # but let's yield just in case
    await asyncio.sleep(0.01)

    assert len(received) == 1
    assert received[0][0] == "device/1/status"
    assert received[0][1] == status

    await pub_connector.disconnect()
    await sub_connector.disconnect()

@pytest.mark.asyncio
async def test_wildcards_and_clearing_retain(local_bus):
    """Test wildcards (+) and clearing retained messages."""
    connector = LocalBusConnector()
    await connector.connect()

    received = []
    async def callback(topic, payload):
        received.append((topic, payload))

    await connector.subscribe("sensors/#", callback)

    # Publish match
    await connector.publish("sensors/kitchen/temp", {"v": 20})
    # Publish non-match
    await connector.publish("logs/kitchen", {"l": "info"})
    # Publish match deep
    await connector.publish("sensors/living/humid/v2", {"v": 50})

    await asyncio.sleep(0.01)
    
    assert len(received) == 2
    assert received[0][0] == "sensors/kitchen/temp"
    assert received[1][0] == "sensors/living/humid/v2"

    # Test Clearing Retained Message
    # 1. Set retain
    await connector.publish("sensors/config", {"cfg": 1}, retain=True)
    # 2. Clear retain (empty payload)
    await connector.publish("sensors/config", {}, retain=True)
    
    # 3. New subscriber shouldn't get anything
    received_new = []
    async def cb_new(t, p): received_new.append(p)
    
    conn2 = LocalBusConnector()
    await conn2.connect()
    await conn2.subscribe("sensors/config", cb_new)
    await asyncio.sleep(0.01)

    assert len(received_new) == 0

    await connector.disconnect()
    await conn2.disconnect()