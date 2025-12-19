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