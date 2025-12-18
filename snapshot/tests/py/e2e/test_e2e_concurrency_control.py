import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


# --- Test Infrastructure: In-Process Communication ---


class InProcessConnector(Connector):
    """
    A Connector that uses asyncio Queues for in-process, in-memory message passing.
    Now supports MQTT-style Retained Messages for robust config delivery.
    """

    _instance = None
    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        # Reset state for each test instantiation if needed,
        # but here we rely on new instances per test via fixtures usually.
        # Since we use class-level dicts for sharing, we should clear them if reusing classes.
        # For this file, let's clear them in __init__ to be safe given the test runner.
        self._shared_topics.clear()
        self._retained_messages.clear()

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        # 1. Handle Retention
        if retain:
            self._retained_messages[topic] = payload

        # 2. Live Dispatch
        # Find all queues subscribed to this topic and put the message
        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)

        # 1. Replay Retained Messages immediately (Async task to simulate network)
        # We find all retained messages that match this new subscription
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await queue.put((retained_topic, payload))

        # 2. Start listener
        asyncio.create_task(self._listen_on_queue(queue, callback))

    async def _listen_on_queue(self, queue: asyncio.Queue, callback):
        while True:
            try:
                topic, payload = await queue.get()
                await callback(topic, payload)
                queue.task_done()
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

    async def set_concurrency_limit(self, scope: str, limit: int):
        constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="concurrency",
            params={"limit": limit},
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


class MockWorkExecutor(Executor):
    """Executor that simulates time-consuming work."""

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        await asyncio.sleep(0.05)
        if kwargs:
            return next(iter(kwargs.values()))
        return "result"


# --- The E2E Test ---


@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller publishes constraint (Retained).
    2. Engine starts, connects, receives config, AND THEN executes.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()

    # 2. Setup the Controller
    controller = ControllerTestApp(connector)

    # 3. Publish the constraint FIRST (Simulating existing environment config)
    # Limit task concurrency to 1
    await controller.set_concurrency_limit(scope="task:slow_task", limit=1)

    # 4. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    # 6. Run the engine (Blocking call, simpler than background task for this flow)
    # The Engine will:
    #   a. Connect
    #   b. Subscribe to constraints/#
    #   c. Receive the retained 'limit=1' message -> Update ConstraintManager
    #   d. Build graph and start scheduling
    #   e. See constraint and throttle execution

    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s.
    assert duration >= 0.18, (
        f"Expected serial execution (~0.2s), but took {duration:.4f}s"
    )
