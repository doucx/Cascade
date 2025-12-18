这是 `cascade-connector-mqtt` 的最后一个核心功能。我们将实现 `subscribe` 方法，允许 Cascade 接收外部指令（例如“暂停”、“恢复”或“更新约束”）。

我们将遵循 TDD 流程：
1.  **编写测试**: 模拟 `aiomqtt` 的消息流，验证订阅的回调函数能否正确接收并处理消息。
2.  **实现功能**: 在 `MqttConnector` 中增加消息监听循环和回调分发逻辑。

## [WIP] feat: Implement subscribe method and message loop for MqttConnector

### 用户需求
完成 `MqttConnector` 的开发，实现 `subscribe` 方法。该方法需要允许注册回调函数，并在收到匹配主题的 MQTT 消息时触发这些回调。

### 评论
实现 `subscribe` 需要引入一个后台消息监听循环 (`message loop`)。当 `connect` 建立连接后，连接器应该启动一个后台任务，持续从 `client.messages` 迭代器中读取消息，并根据 Topic 将其分发给相应的回调函数。这是一个典型的事件驱动模式。

### 目标
1.  在 `tests/test_connector.py` 中添加测试用例：
    *   模拟 `aiomqtt.Client.messages` 作为一个异步迭代器，生成模拟的 MQTT 消息。
    *   验证 `subscribe` 方法是否正确注册了回调。
    *   验证当模拟消息到达时，注册的回调函数是否被调用，且 payload 被正确反序列化。
2.  在 `src/cascade/connectors/mqtt/connector.py` 中：
    *   实现 `_message_loop` 方法，用于持续处理传入消息。
    *   在 `connect` 中启动该循环，在 `disconnect` 中取消该循环。
    *   实现 `subscribe` 方法，记录回调并向 Broker 发送订阅请求。
    *   实现简单的 Topic 匹配逻辑（MVP阶段支持精确匹配）。

### 基本原理
由于 `aiomqtt` 使用异步迭代器处理消息（`async for message in client.messages:`），我们需要在 `connect` 时启动一个非阻塞的 `asyncio.Task` 来运行这个循环。测试的关键在于 Mock 这个异步迭代器，使其产生我们可以断言的数据。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/sync #scope/api #intent/tooling #comp/tests #ai/instruct #task/state/end

---

### Script

#### Acts 1: 编写 `subscribe` 的测试用例 (TDD - Red Phase)

我们需要 Mock `client.messages` 属性。由于 `aiomqtt` 的版本差异，我们假设它是一个可迭代的属性。我们将创建一个辅助的异步迭代器类来模拟它。

~~~~~act
patch_file
packages/cascade-connector-mqtt/tests/test_connector.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: 实现消息循环与 `subscribe` (TDD - Green Phase)

现在我们在 `MqttConnector` 中实现消息监听循环、回调注册以及 Topic 匹配逻辑。

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                json_payload = json.dumps(payload)
                await self._client.publish(topic, payload=json_payload, qos=qos)
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())


    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        # TODO: Implement subscription logic.
        # - The client needs a message handling loop.
        # - This method should register the topic and callback.
        # - The loop will decode JSON and invoke the callback.
        pass
~~~~~
~~~~~python
    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                json_payload = json.dumps(payload)
                await self._client.publish(topic, payload=json_payload, qos=qos)
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        if not self._client:
             logger.warning("Attempted to subscribe without an active MQTT connection.")
             return

        # 1. Register callback locally
        self._subscriptions[topic] = callback

        # 2. Send subscribe command to broker
        try:
            await self._client.subscribe(topic)
        except Exception as e:
             logger.error(f"Failed to subscribe to topic '{topic}': {e}")

    async def _message_loop(self):
        """Background task to process incoming MQTT messages."""
        if not self._client:
            return

        try:
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                # Find callback (Simple exact match for MVP)
                # TODO: Implement wildcard matching if needed (e.g. + or #)
                callback = self._subscriptions.get(topic)
                if not callback:
                    continue

                # Decode and dispatch
                try:
                    # aiomqtt payload can be bytes, bytearray, etc.
                    if isinstance(payload_bytes, (bytes, bytearray)):
                        payload_str = payload_bytes.decode("utf-8")
                    else:
                        payload_str = str(payload_bytes)
                    
                    data = json.loads(payload_str)
                    
                    # Execute callback (fire and forget, or await?)
                    # Since we are in a loop, we should probably await to preserve order,
                    # or create task for concurrency. For now, await is safer for state consistency.
                    await callback(topic, data)

                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON payload on topic '{topic}'")
                except Exception as e:
                    logger.error(f"Error processing message on topic '{topic}': {e}")

        except asyncio.CancelledError:
            # Normal shutdown
            pass
        except Exception as e:
            # Unexpected error in loop, log it. 
            # In a robust system we might want to restart the loop.
            logger.error(f"MQTT message loop crashed: {e}")
~~~~~

#### Acts 3: 完善 `__init__` 和 `connect` 以支持 Loop

我们需要在 `__init__` 中初始化订阅字典和任务句柄，并在 `connect` 中启动任务。

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
    def __init__(self, hostname: str, port: int = 1883, **kwargs):
        if aiomqtt is None:
            raise ImportError(
                "The 'aiomqtt' library is required to use the MqttConnector. "
                "Please install it with: pip install cascade-connector-mqtt"
            )
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        self._client: "aiomqtt.Client" | None = None

    async def connect(self) -> None:
        """Establishes a connection to the MQTT Broker."""
        if self._client:
            return

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname, port=self.port, **self.client_kwargs
        )
        # TODO: Implement LWT message logic.
        self._client = await client.__aenter__()

    async def disconnect(self) -> None:
~~~~~
~~~~~python
    def __init__(self, hostname: str, port: int = 1883, **kwargs):
        if aiomqtt is None:
            raise ImportError(
                "The 'aiomqtt' library is required to use the MqttConnector. "
                "Please install it with: pip install cascade-connector-mqtt"
            )
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        self._client: "aiomqtt.Client" | None = None
        self._loop_task: asyncio.Task | None = None
        self._subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}

    async def connect(self) -> None:
        """Establishes a connection to the MQTT Broker."""
        if self._client:
            return

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname, port=self.port, **self.client_kwargs
        )
        # TODO: Implement LWT message logic.
        self._client = await client.__aenter__()

        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())

    async def disconnect(self) -> None:
~~~~~

### 下一步建议
我们已经完成了 `cascade-connector-mqtt` 包的核心开发，实现了 `connect` (含 Loop 启动)、`disconnect`、`publish` 和 `subscribe`。

根据路线图，**阶段 2 (First Contact)** 的开发工作已经完成：
1.  **协议定义** (`cascade-interfaces`): 已完成。
2.  **引擎集成** (`cascade-runtime`): 已完成。
3.  **连接器实现** (`cascade-connector-mqtt`): 刚刚完成。

现在，我们有几个选择：
1.  **全面测试**: 运行所有测试以确保没有回归。
2.  **示例验证**: 创建一个端到端的集成示例（类似 `examples/telemetry_demo.py`），使用真实的 `Engine` 和 mock 的 `MqttConnector`（或者如果你有本地 Broker）来演示完整的遥测流程。
3.  **进入阶段 3 (约束与环境感知)**: 开始实现全局约束的数据模型和管理器。

考虑到我们是在 monorepo 环境中，我建议先**运行所有测试**，然后**提交**这些更改。提交完成后，我们可以开始 **阶段 3** 的工作。

如果你同意，我将生成一个 `[COMMIT]` 计划。
