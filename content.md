# [WIP] fix: 修复 MQTT 连接器不支持通配符订阅的问题

## 摘要

本计划旨在修复 `MqttConnector` 中存在的一个严重缺陷：其内部消息分发逻辑仅支持精确的主题匹配，导致使用通配符（如 `+` 或 `#`）的订阅（如 `cs-observer` 所使用的）无法接收到消息。

## 错误分析

### 1. `cs-observer` 无输出
*   **现象**: `cs-observer` 订阅了 `cascade/telemetry/+/default/+/events`，Broker 成功发送了 `cascade/telemetry/local/default/run-123/events`，但 `cs-observer` 没有反应。
*   **原因**: 在 `MqttConnector._message_loop` 中，回调函数的查找逻辑是 `callback = self._subscriptions.get(topic)`。这里 `topic` 是从 Broker 收到的**具体主题**（例如 `.../run-123/events`），而 `self._subscriptions` 字典中的 Key 是**订阅模式**（例如 `.../+/events`）。由于这两个字符串不相等，字典查找返回 `None`，导致消息被丢弃。
*   **解决方案**: 实现符合 MQTT 规范的主题匹配逻辑（支持 `+` 和 `#`），并在收到消息时遍历所有订阅进行匹配。

## 用户需求
1.  确保 `cs-observer` 能够显示实时遥测数据。

## 评论
这是一个典型的实现细节疏忽。在之前的 `InProcessConnector`（用于测试的模拟器）中，我们反而正确实现了这个逻辑，但在真实的 `MqttConnector` 中为了简单而使用了字典直接查找。现在必须补齐这个短板。

## 目标
1.  在 `MqttConnector` 中添加 `_topic_matches` 静态方法。
2.  重构 `_message_loop` 以支持通配符匹配分发。

## 基本原理
MQTT 协议定义了 `+`（单层通配符）和 `#`（多层通配符）。客户端库必须在本地实现相应的路由分发逻辑，以便将从 Broker 收到的具体消息映射回最初注册的通配符订阅上。

## 标签
#intent/fix #flow/ready #priority/critical #comp/connector #concept/mqtt #scope/core #ai/instruct #task/domain/telemetry #task/object/connector #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 在 `MqttConnector` 中实现主题匹配逻辑

我们将修改 `connector.py`，添加匹配逻辑并更新循环。

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        if subscription == topic:
            return True
        
        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                # '#' matches the rest of the topic
                return True
            
            if i >= len(topic_parts):
                # Topic is shorter than subscription (and not matched by #)
                return False
            
            topic_part = topic_parts[i]
            
            if sub_part == "+":
                # '+' matches any single level
                continue
            
            if sub_part != topic_part:
                return False
        
        # Ensure lengths match (unless ended with #, handled above)
        return len(sub_parts) == len(topic_parts)

    async def _message_loop(self):
        """Background task to process incoming MQTT messages."""
        if not self._client:
            return

        try:
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                # Dispatch to all matching subscriptions
                # We iterate over all subscriptions because a single message 
                # might match multiple patterns (e.g. "a/b" matches "a/+" and "#")
                matched_callbacks = []
                for sub_pattern, cb in self._subscriptions.items():
                    if self._topic_matches(sub_pattern, topic):
                        matched_callbacks.append(cb)
                
                if not matched_callbacks:
                    continue

                # Decode payload once
                try:
                    # aiomqtt payload can be bytes, bytearray, etc.
~~~~~

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
                    # If the payload is empty (resume command), pass an empty dict
                    if not payload_str:
                        data = {}
                    else:
                        data = json.loads(payload_str)

                    # Execute callback (fire and forget, or await?)
                    # Since we are in a loop, we should probably await to preserve order,
                    # or create task for concurrency. For now, await is safer for state consistency.
                    await callback(topic, data)

                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON payload on topic '{topic}'")
                except Exception as e:
                    logger.error(f"Error processing message on topic '{topic}': {e}")
~~~~~
~~~~~python
                    # If the payload is empty (resume command), pass an empty dict
                    if not payload_str:
                        data = {}
                    else:
                        data = json.loads(payload_str)

                    # Execute all matched callbacks
                    for cb in matched_callbacks:
                        await cb(topic, data)

                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON payload on topic '{topic}'")
                except Exception as e:
                    logger.error(f"Error processing message on topic '{topic}': {e}")
~~~~~

### 下一步建议
应用此补丁后，请再次运行 `cs-observer watch` 和 `workflow_demo.py`。现在 `cs-observer` 应该能够正确匹配并显示遥测数据了。如果验证通过，我们将提交此修复以及之前的所有修复。
