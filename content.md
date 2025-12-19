简要回答
好的，我们开始执行 **萤火计划：里程碑 1.1**。我们将把 `InProcessConnector` 从测试脚手架中提取出来，升级为一个生产级的、位于 `cascade-runtime` 中的 `LocalBusConnector`。

这将为后续的“萤火虫”实验提供一个零延迟、确定性的通信基座。

我们将遵循 TDD 模式：先定义测试规范（Spec），再编写实现。

## [WIP] feat(runtime): Implement LocalBusConnector for in-process signaling

### 用户需求
为了支持“萤火计划”中的单机涌现实验，我们需要一个生产级的、基于内存的消息总线连接器 (`LocalBusConnector`)。它必须支持 MQTT 核心特性（保留消息、通配符订阅），以便在不依赖外部 Broker 的情况下实现 Agent 间的发现与通信。

### 评论
目前的 `InProcessConnector` 隐藏在 `tests/e2e/harness.py` 中。将其提升为一等公民 (`cascade.connectors.local`) 是架构演进的关键一步。这不仅服务于测试，也服务于未来的单机多 Agent 部署模式。

### 目标
1.  创建 `tests/py/connectors/test_local_connector.py`，定义 `LocalBusConnector` 的行为契约（保留消息、通配符、多实例通信）。
2.  在 `cascade-runtime` 包中建立 `cascade.connectors` 命名空间。
3.  实现 `cascade.connectors.local.LocalBusConnector`，移植并增强原有逻辑。

### 基本原理
我们利用 Python 的类属性（Class Attributes）在所有 `LocalBusConnector` 实例间共享状态（Topics 和 Retained Messages）。这种“内存中的单例 Broker”模式非常适合模拟分布式的 MQTT 环境，同时拥有纳秒级的延迟和绝对的确定性。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/telemetry #scope/core
#task/domain/telemetry #task/object/local-bus #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 定义测试规范 (The Spec)

我们首先创建一个专门的测试文件，明确 `LocalBusConnector` 必须满足的三大特性：
1.  **共享总线**: 不同的连接器实例必须能互相通信。
2.  **保留消息**: 必须支持 `retain=True`，即“后来的订阅者也能收到之前的消息”。
3.  **通配符**: 必须支持 `+` (单层) 和 `#` (多层) 匹配。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p tests/py/connectors
~~~~~

~~~~~act
write_file
tests/py/connectors/test_local_connector.py
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: 搭建实现架构

我们需要在 `cascade-runtime` 中创建 `connectors` 包。注意 `__init__.py` 需要包含 `pkgutil` 魔法代码，以支持命名空间扩展。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-runtime/src/cascade/connectors
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/connectors/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-connector-mqtt) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 3: 实现 LocalBusConnector (The Implementation)

移植并增强 `InProcessConnector` 的逻辑，使其成为 `cascade.connectors.local` 模块。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable
from cascade.interfaces.protocols import Connector


class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
    Acts as a local MQTT broker, supporting:
    - Shared state across instances (simulating a network broker)
    - Retained messages
    - Topic wildcards (+ and #)
    """

    # --- Broker State (Shared across all instances) ---
    # topic -> list of (Queue, subscription_pattern)
    # We store the subscription pattern with the queue to verify matches during routing
    _subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}
    _lock = asyncio.Lock()  # Protects shared state modifications

    def __init__(self):
        self._is_connected = False
        self._listener_tasks = []

    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False
        # Cancel all listener tasks for this connector
        for task in self._listener_tasks:
            task.cancel()
        if self._listener_tasks:
            await asyncio.gather(*self._listener_tasks, return_exceptions=True)
        self._listener_tasks.clear()

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._lock:
            # Handle Retention
            if retain:
                if payload == {} or payload == "":
                    # Clear retained message
                    self._retained_messages.pop(topic, None)
                else:
                    # Save retained message
                    self._retained_messages[topic] = payload

            # Route to all matching queues
            # We iterate over all subscription topics in the broker
            for sub_topic, queues in self._subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for q in queues:
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._lock:
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    # For immediate delivery, we can push to queue or call callback directly?
                    # Pushing to queue preserves order and simplifies locking.
                    await queue.put((retained_topic, payload))

        # Start a background listener for this specific subscription queue
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)

    async def _listener_loop(self, queue: asyncio.Queue, callback):
        """Consumes messages from the subscription queue and invokes callback."""
        try:
            while self._is_connected:
                # Use a small timeout or just wait. wait_for allows easier cancellation?
                # A simple await get() is fine as long as we cancel task on disconnect.
                topic, payload = await queue.get()
                try:
                    await callback(topic, payload)
                except Exception as e:
                    # Fail-silent: don't crash the bus because a callback failed
                    print(f"[LocalBus] Callback error on {topic}: {e}")
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        if subscription == "#":
            return True
        if subscription == topic:
            return True

        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                return True

            if i >= len(topic_parts):
                return False

            topic_part = topic_parts[i]

            if sub_part == "+":
                continue

            if sub_part != topic_part:
                return False

        return len(sub_parts) == len(topic_parts)
~~~~~

### 下一步建议
我们已经完成了代码生成。现在应该运行测试 `pytest tests/py/connectors/test_local_connector.py` 来验证实现是否符合 Spec。如果通过，我们将进入 **里程碑 1.2**，开始对引擎核心循环进行“尾递归”改造。
