import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict
import uuid


# --- Test Infrastructure: In-Process Communication ---

class InProcessConnector(Connector):
    """
    A Connector that uses asyncio Queues for in-process, in-memory message passing,
    perfectly simulating a broker for E2E tests without network dependencies.
    """
    _instance = None
    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)

    def __init__(self):
        # This connector acts as a singleton to share state across instances
        pass

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
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
        # Start a listener task for this subscription
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
            return topic.startswith(subscription[:-1])
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
    Full end-to-end test:
    1. A Controller App publishes a concurrency limit.
    2. A running Engine receives it and throttles its execution.
    All communication happens in-memory via the InProcessConnector.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()

    # 2. Setup the Controller
    controller = ControllerTestApp(connector)

    # 3. Define the workflow that will be controlled
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 4. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    # 5. Start the engine in a background task
    engine_task = asyncio.create_task(engine.run(workflow))

    # 6. Wait briefly for the engine to initialize and subscribe to topics
    await asyncio.sleep(0.01)

    # 7. Use the controller to publish the constraint
    await controller.set_concurrency_limit(scope="task:slow_task", limit=1)

    # 8. Await the workflow's completion and measure time
    start_time = time.time()
    results = await engine_task
    duration = time.time() - start_time

    # 9. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s.
    # The time is measured *after* the constraint is published, so it's accurate.
    assert duration >= 0.18, f"Expected serial execution (~0.2s), but took {duration:.4f}s"