import asyncio
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

from cascade.interfaces.protocols import Connector
from cascade.spec.constraint import GlobalConstraint


class InProcessConnector(Connector):
    """
    A deterministic, in-memory connector that simulates an MQTT broker with
    retained message support for robust E2E testing.
    """

    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        # Clear state for each test instance to ensure isolation
        self._shared_topics.clear()
        self._retained_messages.clear()
        self._is_connected = True

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        if retain:
            if payload != {}:  # An empty dict payload is a resume/clear command
                self._retained_messages[topic] = payload
            elif topic in self._retained_messages:
                del self._retained_messages[topic]

        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)

        # Immediately deliver retained messages that match the subscription.
        # We await the callback to ensure state is synchronized before proceeding.
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await callback(retained_topic, payload)

        asyncio.create_task(self._listen_on_queue(queue, callback))

    async def _listen_on_queue(self, queue: asyncio.Queue, callback):
        while self._is_connected:
            try:
                topic, payload = await asyncio.wait_for(queue.get(), timeout=0.1)
                await callback(topic, payload)
                queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False


class ControllerTestApp:
    """A lightweight simulator for the cs-controller CLI tool."""

    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause(self, scope: str = "global"):
        constraint = GlobalConstraint(
            id=f"pause-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="pause",
            params={},
        )
        await self._publish(scope, constraint)

    async def resume(self, scope: str = "global"):
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        # Sending an empty dict simulates the connector's behavior for an empty payload
        await self.connector.publish(topic, {}, retain=True)

    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)
