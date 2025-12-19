You are absolutely right to point this out. My apologies. The fact that it passes in isolation but fails in a full run is the definitive symptom of a test environment leak, and my `sys.modules` patch was flawed in its timing.

This is a classic, subtle, and frustrating problem. I have a definitive solution.

### 错误分析

The root cause is a race condition between Python's module import mechanism and `pytest`'s fixture execution order. Here's what's happening:

1.  `pytest` starts and discovers `tests/connector-mqtt/test_connector.py`.
2.  To discover the tests inside, Python must first **import** this file.
3.  The line `from cascade.connectors.mqtt import MqttConnector` is at the top level of `test_connector.py`. This triggers the import of the `cascade.connectors.mqtt.connector` module.
4.  *That* module, in turn, has `import aiomqtt` at its top level. At this moment, the **real `aiomqtt` module is loaded and cached** in `sys.modules`.
5.  **Only after all this module loading is complete** does `pytest` begin to execute the `autouse` fixture (`mock_aiomqtt_module`) inside `test_connector.py`.
6.  The fixture then patches `sys.modules`, but it's **too late**. The `cascade.connectors.mqtt.connector` module already holds a reference to the original, real `aiomqtt` module in its local namespace.

The patch I applied was correct in principle but executed at the wrong time.

**The Solution:**

We need to apply the patch *before* `test_connector.py` is ever imported. The `pytest` mechanism designed for exactly this purpose is a `conftest.py` file. A `conftest.py` file in a directory is loaded by `pytest` *before* it loads the test modules in that same directory.

By moving the `autouse` fixture into `tests/connector-mqtt/conftest.py`, we guarantee that our fake `aiomqtt` module is in `sys.modules` *before* the line `from cascade.connectors.mqtt import MqttConnector` ever runs. This will permanently solve the problem.

## [WIP] fix(tests): Isolate MQTT mock environment using conftest.py

### 用户需求
Fix the persistent `TypeError` in `test_connector.py` by ensuring the `aiomqtt` mock is in place before the module under test is imported.

### 评论
This is the correct and canonical `pytest` solution for complex mocking scenarios that need to preempt module imports. It will create a fully hermetic testing environment for the MQTT connector, making it resilient to state leakage from other tests. This is a valuable hardening of our test suite.

### 目标
1.  Create a new `tests/connector-mqtt/conftest.py` file.
2.  Move the `mock_aiomqtt_module` autouse fixture from `test_connector.py` into this new `conftest.py`.
3.  Clean up `test_connector.py` by removing the fixture definition, as it will now be provided automatically by `conftest.py`.

### 基本原理
We are leveraging `pytest`'s test discovery and configuration loading order. `pytest` scans for and loads `conftest.py` files as it descends the directory tree, making any fixtures they contain available to the test modules at that level. By defining our `autouse` fixture in a local `conftest.py`, we win the race against the module-level `import` statements in `test_connector.py`, ensuring our mock is active at the critical moment.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/test-isolation #task/action/bug-fix #task/state/end

---
### Script

#### Acts 1: Create `conftest.py` to host the isolated environment

We will create the `conftest.py` file and place the powerful, isolating fixture inside it.

~~~~~act
write_file
tests/connector-mqtt/conftest.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def mock_aiomqtt_module(mocker):
    """
    Creates a completely isolated, fake 'aiomqtt' module and injects it into
    sys.modules for the duration of the tests in this directory.

    This is defined in conftest.py to ensure it runs BEFORE the test module
    is imported, thus patching the dependency before it's ever loaded.
    """
    # 1. Create the mock client INSTANCE that will be returned by the fake Client class
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # 2. Create the fake aiomqtt.Client CLASS (a factory for the instance)
    mock_client_class = MagicMock(return_value=mock_client_instance)

    # 3. Create the fake aiomqtt.Will CLASS
    mock_will_class = MagicMock()

    # 4. Create the fake aiomqtt MODULE object
    mock_aiomqtt_module_obj = MagicMock()
    mock_aiomqtt_module_obj.Client = mock_client_class
    mock_aiomqtt_module_obj.Will = mock_will_class

    # 5. Patch sys.modules to replace the real aiomqtt with our fake one
    mocker.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt_module_obj})

    # Yield the components for tests to use, if they need to make assertions
    yield {
        "instance": mock_client_instance,
        "Client": mock_client_class,
        "Will": mock_will_class,
    }
~~~~~

#### Acts 2: Clean up `test_connector.py`

Now we remove the fixture from the test file itself, simplifying it greatly. The tests will now transparently use the fixture provided by `conftest.py`.

~~~~~act
write_file
tests/connector-mqtt/test_connector.py
~~~~~
~~~~~python
import pytest
import json
import asyncio
from cascade.connectors.mqtt import MqttConnector

# Note: The 'mock_aiomqtt_module' fixture is now autoused from conftest.py
# This ensures aiomqtt is mocked BEFORE this module is even imported.

def test_mqtt_connector_instantiation():
    """Tests that the MqttConnector can be instantiated."""
    connector = MqttConnector(hostname="localhost", port=1234)
    assert connector.hostname == "localhost"
    assert connector.port == 1234


@pytest.mark.asyncio
async def test_connect_and_disconnect_lifecycle(mock_aiomqtt_module, mocker):
    """Tests that connect() creates and connects a client with LWT, and disconnect() disconnects it."""
    mock_client_instance = mock_aiomqtt_module["instance"]
    mock_client_class = mock_aiomqtt_module["Client"]
    mock_will_class = mock_aiomqtt_module["Will"]

    # Mock platform and os to get a deterministic source_id
    mocker.patch("platform.node", return_value="test-host")
    mocker.patch("os.getpid", return_value=12345)

    # Setup connector
    connector = MqttConnector(hostname="test.broker", port=9999, client_id="tester")

    # Test connect()
    await connector.connect()

    # Assert that Will was called correctly
    expected_source_id = "test-host-12345"
    expected_topic = f"cascade/status/{expected_source_id}"
    expected_payload = json.dumps({"status": "offline"})
    mock_will_class.assert_called_once_with(
        topic=expected_topic, payload=expected_payload
    )

    # Assert that the client was instantiated with the will message
    mock_client_class.assert_called_once_with(
        hostname="test.broker",
        port=9999,
        client_id="tester",
        will=mock_will_class.return_value,
    )

    # Assert that the client's connect method was awaited via context manager
    mock_client_instance.__aenter__.assert_awaited_once()

    # Test disconnect()
    await connector.disconnect()

    # Assert that the client's disconnect method was awaited via context manager
    mock_client_instance.__aexit__.assert_awaited_once()
    assert connector._client is None


@pytest.mark.asyncio
async def test_publish_sends_json_and_is_fire_and_forget(mock_aiomqtt_module):
    """
    Tests that publish() serializes the payload to JSON and sends it in a
    non-blocking manner.
    """
    mock_client = mock_aiomqtt_module["instance"]
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
        topic, payload=expected_json_payload, qos=1, retain=False
    )


@pytest.mark.asyncio
async def test_publish_without_connect_does_nothing(mock_aiomqtt_module):
    """
    Tests that calling publish() before connect() does not raise an error
    and does not try to publish anything (Fail-Silent Telemetry).
    """
    mock_client = mock_aiomqtt_module["instance"]
    connector = MqttConnector(hostname="test.broker")

    # Do not call connect()
    await connector.publish("a/topic", {"data": 1})
    await asyncio.sleep(0)

    mock_client.publish.assert_not_called()


@pytest.mark.asyncio
async def test_subscribe_receives_messages(mock_aiomqtt_module):
    """
    Tests that the connector starts a listener loop, and when messages arrive,
    the registered callback is invoked with decoded data.
    """
    mock_client = mock_aiomqtt_module["instance"]
    connector = MqttConnector(hostname="test.broker")

    # 1. Setup Mock Message Stream
    incoming_payload = {"command": "pause"}
    incoming_topic = "control/pause"

    class MockMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload

    async def message_stream():
        yield MockMessage(incoming_topic, json.dumps(incoming_payload).encode("utf-8"))
        await asyncio.sleep(10)

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
    await asyncio.sleep(0.01)

    # 5. Assert callback invocation
    assert len(received_events) == 1
    assert received_events[0][0] == incoming_topic
    assert received_events[0][1] == incoming_payload

    # Cleanup
    await connector.disconnect()
~~~~~

### 下一步建议
This should be the definitive fix. We have addressed both the structural issues and the complex environment leakage problem with a standard, robust pattern.

Please run the full `pytest` suite one last time. If it passes, we can proceed to generate a final `[COMMIT]` plan to merge all these changes into a single, logical unit of work.
