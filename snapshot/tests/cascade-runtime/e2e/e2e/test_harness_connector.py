import pytest
import asyncio
from .harness import InProcessConnector

@pytest.mark.asyncio
async def test_in_process_connector_plus_wildcard_subscription():
    """
    Isolated test to verify that the InProcessConnector correctly handles
    the single-level '+' MQTT wildcard in subscriptions.
    """
    connector = InProcessConnector()
    received_payloads = []

    async def observer_callback(topic, payload):
        received_payloads.append(payload)

    # 1. ARRANGE: Subscribe with a '+' wildcard
    subscription_topic = "test/+/data"
    await connector.subscribe(subscription_topic, observer_callback)

    # 2. ACT: Publish to a topic that should match the wildcard
    publish_topic = "test/device-123/data"
    await connector.publish(publish_topic, {"value": 42})
    
    # Give the internal queue a moment to process
    await asyncio.sleep(0.01)

    # 3. ASSERT: The message should have been received
    assert len(received_payloads) == 1, (
        f"Connector failed to route message on topic '{publish_topic}' "
        f"to wildcard subscription '{subscription_topic}'"
    )
    assert received_payloads[0] == {"value": 42}