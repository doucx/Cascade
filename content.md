你的分析和观察非常及时。通过审视 `harness.py` 中的 `InProcessConnector` 和生产环境的 `MqttConnector`，我们发现 `InProcessConnector` 虽然已经具备了核心逻辑（如保留消息和通配符），但它仍然是一个“非正式”的实现，缺乏规范的生命周期管理和严格的 MQTT 行为模拟。

我们将启动 **萤火计划：里程碑 1.1**，将这一 Mock 实现正规化为 `LocalBusConnector`。

## [WIP] feat(runtime): 实现 LocalBusConnector 以支持零配置的 Agent 协作

### 用户需求
需要一个生产级的、基于内存的连接器（`LocalBusConnector`），它在同一个进程内模拟 MQTT Broker 的行为（包括保留消息和通配符匹配），为后续的“萤火虫” Agent 提供低延迟、确定性的通信底座。

### 评论
这是“萤火计划”的基础。通过在 `cascade-runtime` 中提供一个正式的本地总线连接器，我们不仅优化了测试体验，更重要的是为“单机多 Agent”场景提供了一个无需依赖外部环境（如 Mosquitto）的运行环境。这符合我们的“零强制依赖”原则。

### 目标
1.  在 `cascade-runtime` 中创建 `cascade.connectors.local` 包。
2.  实现 `LocalBusConnector` 类，确保其行为与 `MqttConnector` 高度一致。
3.  建立专门的测试套件，验证通配符匹配、保留消息同步以及并发分发的正确性。

### 基本原理
我们将 `InProcessConnector` 的简单逻辑与 `MqttConnector` 的严谨协议实现结合。核心是利用类属性（Class Attributes）来维持进程内的“全局单例总线”，并使用 `asyncio.Queue` 确保消息分发的非阻塞性。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/dx #ai/delegate #task/domain/runtime #task/object/local-bus #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 `LocalBusConnector` 的核心实现

我们将实现放置在 `cascade-runtime` 包下，使其成为核心适配器的一部分。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-runtime/src/cascade/connectors/local
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
import asyncio
import json
import logging
from typing import Callable, Awaitable, Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

class LocalBusConnector:
    """
    一个基于内存的连接器，模拟 MQTT Broker 在单个进程内的行为。
    它使用类属性来确保在同一个 Python 进程中，所有连接器实例共享同一个“虚拟总线”。
    """

    # 共享的订阅池: {topic_pattern: [Queue]}
    _shared_queues: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    # 共享的保留消息池: {topic: payload}
    _retained_messages: Dict[str, Any] = {}
    # 互斥锁，保护对共享状态的修改
    _lock = asyncio.Lock()

    def __init__(self):
        self._is_connected = False
        self._listener_tasks: List[asyncio.Task] = []
        self._subscriptions: Dict[str, Callable] = {}

    async def connect(self) -> None:
        """模拟建立连接。"""
        self._is_connected = True
        logger.debug("LocalBusConnector connected.")

    async def disconnect(self) -> None:
        """断开连接并取消所有本地监听任务。"""
        self._is_connected = False
        for task in self._listener_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listener_tasks.clear()
        logger.debug("LocalBusConnector disconnected.")

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        """
        发布消息到虚拟总线。
        如果 retain=True，消息会被存入保留消息池。
        """
        if not self._is_connected:
            logger.warning("Attempted to publish to LocalBus while disconnected.")
            return

        async with self._lock:
            if retain:
                if payload == {} or payload == "":
                    # 模拟 MQTT: 发布空负载到保留主题即为删除该保留消息
                    if topic in self._retained_messages:
                        del self._retained_messages[topic]
                else:
                    self._retained_messages[topic] = payload

            # 寻找所有匹配的订阅队列
            for sub_pattern, queues in self._shared_queues.items():
                if self._topic_matches(sub_pattern, topic):
                    for q in queues:
                        # 非阻塞放入队列
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """
        订阅特定主题或通配符。
        订阅成功后，会立即同步分发现有的匹配保留消息。
        """
        if not self._is_connected:
            logger.warning("Attempted to subscribe to LocalBus while disconnected.")
            return

        queue = asyncio.Queue()
        
        async with self._lock:
            self._shared_queues[topic].append(queue)
            
            # 立即投递匹配的保留消息
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    # 为了保证确定性，在本地总线中我们直接 await 回调
                    # 确保在 subscribe 返回前，保留消息已经处理完毕
                    await callback(retained_topic, payload)

        # 启动后台监听循环
        task = asyncio.create_task(self._listen_loop(queue, callback))
        self._listener_tasks.append(task)

    async def _listen_loop(self, queue: asyncio.Queue, callback: Callable):
        """处理该订阅的消息循环。"""
        while self._is_connected:
            try:
                topic, payload = await queue.get()
                await callback(topic, payload)
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in LocalBus listener: {e}")

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        MQTT 通配符匹配算法实现（支持 + 和 #）。
        复用自 MqttConnector。
        """
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

    @classmethod
    async def reset_bus(cls):
        """
        清理全局共享状态，主要用于测试隔离。
        """
        async with cls._lock:
            cls._shared_queues.clear()
            cls._retained_messages.clear()
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/connectors/local/__init__.py
~~~~~
~~~~~python
from .connector import LocalBusConnector

__all__ = ["LocalBusConnector"]
~~~~~

#### Acts 2: 编写 TDD 测试套件

我们将创建一个新的测试文件，专门验证 `LocalBusConnector` 的生产级行为。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p tests/connector-local
~~~~~

~~~~~act
write_file
tests/connector-local/test_local.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.connectors.local import LocalBusConnector

@pytest.fixture(autouse=True)
async def cleanup_bus():
    """每个测试运行前强制清理全局总线。"""
    await LocalBusConnector.reset_bus()
    yield

@pytest.mark.asyncio
async def test_local_bus_broadcast():
    """测试基本的消息广播功能。"""
    c1 = LocalBusConnector()
    c2 = LocalBusConnector()
    
    received = []
    async def cb(topic, payload):
        received.append(payload)

    await c1.connect()
    await c2.connect()
    
    await c1.subscribe("news/tech", cb)
    await c2.publish("news/tech", {"msg": "hello"})
    
    await asyncio.sleep(0.01)
    assert received == [{"msg": "hello"}]
    
    await c1.disconnect()
    await c2.disconnect()

@pytest.mark.asyncio
async def test_retained_messages_sync():
    """
    验证保留消息的核心特性：
    后订阅的实例必须能立即收到之前发布的保留消息。
    """
    publisher = LocalBusConnector()
    subscriber = LocalBusConnector()
    
    await publisher.connect()
    await subscriber.connect()
    
    # 1. 先发布保留消息
    await publisher.publish("config/global", {"timeout": 30}, retain=True)
    
    # 2. 后订阅
    received = []
    async def cb(topic, payload):
        received.append(payload)
    
    # subscribe 应该在返回前执行回调（针对保留消息）
    await subscriber.subscribe("config/global", cb)
    
    assert received == [{"timeout": 30}], "Subscriber should receive retained message immediately"

@pytest.mark.asyncio
async def test_wildcard_matching():
    """测试多级通配符匹配。"""
    connector = LocalBusConnector()
    await connector.connect()
    
    received = []
    async def cb(topic, payload):
        received.append(topic)

    await connector.subscribe("sensors/#", cb)
    
    await connector.publish("sensors/temp/room1", {"v": 20})
    await connector.publish("sensors/humidity", {"v": 60})
    await connector.publish("lights/kitchen", {"v": "on"}) # 不匹配
    
    await asyncio.sleep(0.01)
    assert "sensors/temp/room1" in received
    assert "sensors/humidity" in received
    assert "lights/kitchen" not in received

@pytest.mark.asyncio
async def test_clear_retained_message():
    """测试清理保留消息（发布空负载）。"""
    bus = LocalBusConnector()
    await bus.connect()
    
    await bus.publish("test/topic", "stay", retain=True)
    await bus.publish("test/topic", "", retain=True) # 清理
    
    received = []
    async def cb(t, p): received.append(p)
    
    await bus.subscribe("test/topic", cb)
    assert len(received) == 0
~~~~~

### 下一步建议
1.  **运行测试**：确保 `tests/connector-local/test_local.py` 全部通过。
2.  **替换旧引用**：将 `tests/py/e2e/harness.py` 中的 `InProcessConnector` 替换为对 `LocalBusConnector` 的引用。
3.  **进入 Milestone 1.2**：开始对 `Engine` 进行重构，以支持 TCO（尾调用优化）风格的递归。这将涉及修改 `Engine.run` 的主循环。
