import asyncio
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

from typing import List
from cascade.interfaces.protocols import Connector, Executor
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class MockWorkExecutor(Executor):
    """Executor that simulates short, time-consuming work."""

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Yield control to event loop to simulate async boundary
        await asyncio.sleep(0)
        if kwargs:
            return next(iter(kwargs.values()))
        return "done"


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

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                # '#' matches the rest of the topic, so it's a match
                return True

            if i >= len(topic_parts):
                # Topic is shorter than subscription pattern (and not matched by #)
                return False

            topic_part = topic_parts[i]

            if sub_part == "+":
                # '+' matches any single level, so we continue to the next part
                continue

            if sub_part != topic_part:
                # Literal parts do not match
                return False

        # If we finished the loop, it's a match IFF the lengths are the same.
        # (The '#' case is handled inside the loop)
        return len(sub_parts) == len(topic_parts)


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
