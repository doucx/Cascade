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


# --- Reusing InProcessConnector (Ideally this should be a shared fixture) ---
class InProcessConnector(Connector):
    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        self._shared_topics.clear()
        self._retained_messages.clear()

    async def connect(self) -> None: pass
    async def disconnect(self) -> None: pass

    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        if retain:
            if payload:
                self._retained_messages[topic] = payload
            elif topic in self._retained_messages:
                del self._retained_messages[topic]
        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await callback(retained_topic, payload)
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
        if subscription == topic: return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix): return True
        return False


class ControllerTestApp:
    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause_with_ttl(self, scope: str, ttl: int):
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


class MockWorkExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        return "done"


@pytest.mark.asyncio
async def test_e2e_ttl_expiration():
    """
    Tests that a pause constraint automatically expires after TTL.
    """
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await controller.pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
    def simple_task():
        return True

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    start_time = time.time()
    
    # 2. Run engine. It should be paused initially.
    # The Engine loop will wait on wakeup.
    # ConstraintManager should have scheduled a wakeup at T+0.25s.
    # At T+0.25s, Engine wakes up, cleans expired constraint, and unblocks.
    await engine.run(workflow)
    
    duration = time.time() - start_time

    # 3. Assertions
    # Duration must be at least the TTL (0.25s), proving it was blocked.
    assert duration >= 0.24, f"Engine didn't wait for TTL! Duration: {duration:.3f}s"
    
    # But it shouldn't wait forever (e.g. < 1s)
    assert duration < 1.0, "Engine waited too long or didn't recover."