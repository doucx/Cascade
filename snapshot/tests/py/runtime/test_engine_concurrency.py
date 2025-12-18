import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node


# --- Mocks ---

class MockConnector(Connector):
    """A mock connector for testing Engine's subscription logic."""

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        pass

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        for sub_topic, callback in self.subscriptions.items():
            is_match = False
            if sub_topic == topic:
                is_match = True
            elif sub_topic.endswith("/#"):
                prefix = sub_topic[:-2]
                if topic.startswith(prefix):
                    is_match = True

            if is_match:
                await callback(topic, payload)


class MockExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Simulate work duration
        await asyncio.sleep(0.05)
        return args[0] if args else "result"


# --- Fixtures ---

@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=mock_connector,
        # Ensure system has infinite capacity by default unless constrained
        system_resources={}, 
    )


# --- Tests ---

@pytest.mark.asyncio
async def test_concurrency_constraint_on_map(engine, mock_connector):
    """
    Verify that a concurrency constraint limits the parallelism of a mapped task.
    """
    @cs.task
    def slow_task(x):
        return x

    # 1. Map over 4 items. Without constraint, they should run in parallel (~0.05s total).
    inputs = [1, 2, 3, 4]
    workflow = slow_task.map(x=inputs)

    # 2. Inject constraint BEFORE running (simulating a pre-existing retained message)
    # We do this by manually triggering the update, assuming the engine subscribes early.
    # However, Engine subscribes inside run().
    # So we must start run(), wait for subscription, then inject constraint.
    
    # But wait, to test effect on the whole map, we need the constraint active before tasks schedule.
    # The standard way is that 'run' connects and subscribes first.
    # So we trigger the message immediately after run starts but before tasks are processed?
    # Or rely on the fact that Mapped tasks expand into sub-graphs dynamically.
    
    # A cleaner way for this test:
    # Use a background task to run the engine.
    task_future = asyncio.create_task(engine.run(workflow))
    
    # Give engine time to connect and subscribe
    await asyncio.sleep(0.01)
    
    # 3. Inject Concurrency Constraint: limit 'slow_task' to 1 concurrent instance.
    scope = "task:slow_task"
    payload = {
        "id": "limit-slow-task",
        "scope": scope,
        "type": "concurrency",
        "params": {"limit": 1}
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{scope.replace(':', '/')}", payload
    )
    
    # 4. Measure execution time
    start_time = time.time()
    results = await task_future
    duration = time.time() - start_time
    
    assert sorted(results) == [1, 2, 3, 4]
    
    # With limit=1, 4 tasks of 0.05s should take >= 0.2s
    # Without limit, it would be ~0.05s
    assert duration >= 0.2, f"Expected serial execution duration >= 0.2s, got {duration}s"


@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    """
    Verify that a global concurrency constraint limits total tasks running.
    """
    @cs.task
    def task_a(x): return x
    
    @cs.task
    def task_b(x): return x

    # Two independent tasks, normally run in parallel
    wf = [task_a(1), task_b(2)]
    
    # Wrapper to run list of tasks
    @cs.task
    def wrapper(results): return results
    
    workflow = wrapper(wf) # Engine.run handles the list dependency resolution inside wrapper args

    task_future = asyncio.create_task(engine.run(workflow))
    await asyncio.sleep(0.01)

    # Inject Global Limit = 1
    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1}
    }
    await mock_connector._trigger_message("cascade/constraints/global", payload)

    start_time = time.time()
    await task_future
    duration = time.time() - start_time
    
    # 2 tasks of 0.05s in serial => >= 0.1s
    assert duration >= 0.1, f"Expected serial execution duration >= 0.1s, got {duration}s"
