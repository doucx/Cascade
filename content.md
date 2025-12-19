你的分析非常精准。

1.  **环境泄漏**: 测试套件在全量运行时失败，但在独立运行时通过，这是测试间**状态污染**或**环境泄漏**的典型症状。一个测试的 Mock 或配置影响了后续测试的运行环境。
2.  **目录结构错误**: `tests/cascade-runtime/runtime/runtime/` 这样的重复路径表明我之前的 `move_file` 操作是错误的。`move_file a b` 会将目录 `a` 移动到目录 `b` *之下*，而不是移动 `a` 的*内容*。我需要纠正这个错误。

我将制定一个两阶段的计划来解决这两个问题。首先，修复错误的目录结构；其次，采用一种更强大的、完全隔离的 Mocking 策略来根除环境泄漏问题。

## [WIP] fix(tests): 修正测试目录结构并隔离 MQTT Mock 环境

### 错误分析

**1. 目录结构问题**

我之前计划中的 `move_file tests/py/runtime tests/cascade-runtime/runtime` 等指令，错误地将源目录（例如 `runtime`）移动到了目标目录 `tests/cascade-runtime/runtime` *内部*，导致了 `.../runtime/runtime/` 这样的嵌套。正确的做法应该是将源目录的*内容*移动到目标目录。我将通过一系列更精确的 `move_file` 操作来修正这个问题。

**2. 测试环境泄漏**

`test_connector.py` 的失败根源在于，当全量运行时，`aiomqtt` 模块在被 `mocker` patch 之前，已经被某个先行的测试以某种方式“污染”了。为了彻底杜绝这种可能性，我们将采用一种终极的隔离策略：

*   **完全模块替换**: 我们不再 `patch` `aiomqtt.Client` 这个类，而是在 `test_connector.py` 的测试开始前，直接从 `sys.modules` 中**移除**整个 `aiomqtt` 模块（如果存在的话），并用一个我们完全控制的 `MagicMock` 对象取而代之。
*   **确定性行为**: 这个伪造的 `aiomqtt` 模块将有一个 `Client` 属性，该属性是一个 Mock 工厂，它在被调用时会返回我们预先配置好的 `AsyncMock` 实例。

这个方案有两个巨大优势：
1.  **完全隔离**: 它确保了 `test_connector.py` 中的测试与系统中其他任何地方对 `aiomqtt` 的使用完全无关。
2.  **可选依赖测试**: 它甚至不要求 `aiomqtt` 被实际安装，使得测试在没有可选依赖的环境中也能健壮运行。

### 用户需求
1.  修复 `tests` 目录下因错误的文件移动操作导致的重复和嵌套的目录结构。
2.  修复 `test_connector.py` 在全量测试时因环境泄漏导致的 `TypeError` 失败。

### 评论
这是一个关键的修复计划。一个干净、可预测的测试环境是项目长期健康发展的基石。通过修正结构并加强测试隔离，我们不仅解决了当前的 bug，也为未来的测试套件增加了韧性。

### 目标
1.  执行一系列 `move_file` 操作，将嵌套目录中的测试文件移动到其正确的、扁平化的位置。
2.  删除因错误移动而产生的多余的嵌套目录。
3.  在 `test_connector.py` 中引入一个新的 `autouse` Fixture，该 Fixture 使用 `mocker.patch.dict('sys.modules', ...)` 来创建一个完全隔离的、伪造的 `aiomqtt` 模块。
4.  简化 `test_connector.py` 中现有的 Mocking 代码，使其依赖于这个新的、全局隔离的 Mock 环境。

### 基本原理
我们将分两步走。第一步是通过精细的文件移动操作“解开”错误的目录嵌套。第二步是在 `test_connector.py` 中建立一个“无尘室”环境：通过 `autouse` 的 `pytest` Fixture，在文件内的所有测试运行前，用一个我们精心构造的 Mock 对象在 Python 的模块缓存 (`sys.modules`) 中替换掉 `aiomqtt`，从而保证测试的输入是完全确定的，不受任何外部状态干扰。

### 标签
#intent/fix #intent/refine #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/test-isolation #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 修正 `cascade-runtime` 内部错误的目录结构

我们将逐一修正 `tests/cascade-runtime` 下的嵌套目录。

~~~~~act
run_command
~~~~~
~~~~~bash
# Move contents of adapters/adapters up one level, then remove the empty dir
mv tests/cascade-runtime/adapters/adapters/* tests/cascade-runtime/adapters/
rmdir tests/cascade-runtime/adapters/adapters

# Move contents of connectors/connectors up one level, then remove the empty dir
mv tests/cascade-runtime/connectors/connectors/* tests/cascade-runtime/connectors/
rmdir tests/cascade-runtime/connectors/connectors

# Move contents of e2e/e2e up one level, then remove the empty dir
mv tests/cascade-runtime/e2e/e2e/* tests/cascade-runtime/e2e/
rmdir tests/cascade-runtime/e2e/e2e

# Move contents of graph/graph up one level, then remove the empty dir
mv tests/cascade-runtime/graph/graph/* tests/cascade-runtime/graph/
rmdir tests/cascade-runtime/graph/graph

# Move contents of integration/integration up one level, then remove the empty dir
mv tests/cascade-runtime/integration/integration/* tests/cascade-runtime/integration/
rmdir tests/cascade-runtime/integration/integration

# Move contents of runtime/runtime up one level, then remove the empty dir
mv tests/cascade-runtime/runtime/runtime/* tests/cascade-runtime/runtime/
rmdir tests/cascade-runtime/runtime/runtime
~~~~~

#### Acts 2: 修正 `cascade-py` 内部错误的目录结构

同样地，修正 `cascade-py` 下的嵌套目录。

~~~~~act
run_command
~~~~~
~~~~~bash
# Move contents of examples/examples up one level, then remove the empty dir
mv tests/cascade-py/examples/examples/* tests/cascade-py/examples/
rmdir tests/cascade-py/examples/examples

# Move contents of providers/providers up one level, then remove the empty dir
mv tests/cascade-py/providers/providers/* tests/cascade-py/providers/
rmdir tests/cascade-py/providers/providers

# Move contents of tools/tools up one level, then remove the empty dir
mv tests/cascade-py/tools/tools/* tests/cascade-py/tools/
rmdir tests/cascade-py/tools/tools
~~~~~

#### Acts 3: 实现完全隔离的 MQTT Mock 环境

现在，我们对 `test_connector.py` 进行手术，注入终极隔离的 Mock Fixture。这将替换掉之前所有的 `mocker.patch` 尝试。

~~~~~act
write_file
tests/connector-mqtt/test_connector.py
~~~~~
~~~~~python
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from cascade.connectors.mqtt import MqttConnector

# Attempt to import aiomqtt for type hinting if available, but don't fail
try:
    import aiomqtt
except ImportError:
    aiomqtt = None


@pytest.fixture(autouse=True)
def mock_aiomqtt_module(mocker):
    """
    Creates a completely isolated, fake 'aiomqtt' module and injects it into
    sys.modules for the duration of the tests in this file.

    This prevents any state leakage from other tests and removes the need for
    aiomqtt to be installed to run these tests.
    """
    # 1. Create the mock client INSTANCE that will be returned by the fake Client class
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # 2. Create the fake aiomqtt.Client CLASS
    mock_client_class = MagicMock(return_value=mock_client_instance)

    # 3. Create the fake aiomqtt.Will CLASS
    mock_will_class = MagicMock()

    # 4. Create the fake aiomqtt MODULE
    mock_aiomqtt_module = MagicMock()
    mock_aiomqtt_module.Client = mock_client_class
    mock_aiomqtt_module.Will = mock_will_class

    # 5. Patch sys.modules to replace the real aiomqtt with our fake one
    mocker.patch.dict(
        "sys.modules", {"aiomqtt": mock_aiomqtt_module}
    )

    # Yield the components for tests to use
    yield {
        "instance": mock_client_instance,
        "Client": mock_client_class,
        "Will": mock_will_class,
    }


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

    # 2. Setup connector
    connector = MqttConnector(hostname="test.broker", port=9999, client_id="tester")

    # 3. Test connect()
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

    # 4. Test disconnect()
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
我们已经完成了两个关键的修复：
1.  整理了 `tests` 目录的结构，消除了令人困惑的嵌套。
2.  为 `test_connector.py` 引入了目前已知最健壮的 Mock 隔离策略。

现在，请最后一次运行完整的 `pytest` 测试套件。如果所有测试都通过了，那么这次大规模的重构就成功了，我们可以将其作为一个完整的、可提交的工作单元。
