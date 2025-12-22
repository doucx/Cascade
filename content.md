为了诊断这个 `LocalBusConnector` 的问题，我需要在 `LocalBusConnector` 里加日志。

## [WIP] chore(debug): 深入 LocalBusConnector 调试

### 用户需求
在 `LocalBusConnector` 的 `publish`, `subscribe`, `_topic_matches` 中添加日志，查明为何消息没有路由到 Engine。

### 评论
这是最后一公里的调试。肯定是连接器这边的逻辑有个微小的偏差。

### 目标
修改 `packages/cascade-connector-local/src/cascade/connectors/local/bus.py`。

### 标签
#intent/tooling #flow/ready #priority/high #comp/debug #scope/core #ai/instruct

---

### Script

#### Acts 1: 在 `LocalBusConnector` 中插桩

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._get_lock():
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        print(f"DEBUG: Connector publish {topic} connected={self._is_connected}")
        if not self._is_connected:
            return

        async with self._get_lock():
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~
~~~~~python
            # 2. Wildcard Matches (O(W))
            for sub_topic, queues in self._wildcard_subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for q in queues:
                        await q.put((topic, payload))
~~~~~
~~~~~python
            # 2. Wildcard Matches (O(W))
            for sub_topic, queues in self._wildcard_subscriptions.items():
                match = self._topic_matches(sub_topic, topic)
                print(f"DEBUG: Checking match sub='{sub_topic}' topic='{topic}' -> {match}. Queues: {len(queues)}")
                if match:
                    for q in queues:
                        await q.put((topic, payload))
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        print(f"DEBUG: Connector subscribe {topic}")
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()
~~~~~

### 下一步建议

再次运行测试。这次我们应该能看清 Connector 内部发生了什么。

**可能的剧本：**
*   `Connector publish` 打印了，但 `Checking match` 没打印：说明 `_wildcard_subscriptions` 是空的。这意味着 `subscribe` 没成功或者被清理了。
*   `Checking match` 打印了但结果是 `False`：说明 `_topic_matches` 逻辑有漏洞。
*   `Checking match` 是 `True` 但 `Queues` 是 0：说明订阅列表空了。

运行吧！
