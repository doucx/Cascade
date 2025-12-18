import asyncio
import time
import pytest
from typing import Callable, Awaitable, Dict, Any, List

from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.spec.task import task

# Mock Components

class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}

    async def connect(self) -> None: pass
    async def disconnect(self) -> None: pass
    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None: pass

    async def subscribe(self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]) -> None:
        self.subscriptions[topic] = callback

    async def trigger(self, topic: str, payload: Dict[str, Any]):
        for sub_topic, callback in self.subscriptions.items():
            if sub_topic == topic or sub_topic == "cascade/constraints/#":
                await callback(topic, payload)

class RealAsyncExecutor(Executor):
    """An executor that actually runs async tasks, to allow testing concurrency timing."""
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]) -> Any:
        if node.callable_obj:
            return await node.callable_obj(*args, **kwargs)
        return None

# Fixtures

@pytest.fixture
def connector():
    return MockConnector()

@pytest.fixture
def engine(connector):
    return Engine(
        solver=NativeSolver(),
        executor=RealAsyncExecutor(),
        bus=MessageBus(),
        connector=connector,
        # Give enough system resources so we aren't bottlenecked by anything else
        system_resources={"cpu": 100},
    )

# Tests

@pytest.mark.asyncio
async def test_concurrency_constraint_serialization(engine, connector):
    """
    Verify that injecting a concurrency constraint limits parallel execution.
    """
    # 1. Define a task that takes time
    @task
    async def slow_task(x: int):
        await asyncio.sleep(0.05)
        return x

    # 2. Map it over 4 items. Without constraint, should finish in ~0.05s (parallel)
    # With limit=1, should take ~0.20s (serial)
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 3. Start engine
    run_task = asyncio.create_task(engine.run(workflow))
    
    # Wait for engine to connect
    await asyncio.sleep(0.01)

    # 4. Inject Concurrency Limit = 1 for 'slow_task'
    constraint_payload = {
        "id": "limit-slow-task",
        "scope": "task:slow_task",
        "type": "concurrency",
        "params": {"limit": 1},
    }
    await connector.trigger("cascade/constraints/limit", constraint_payload)

    # 5. Measure time
    start = time.time()
    results = await run_task
    duration = time.time() - start

    assert sorted(results) == [1, 2, 3, 4]

    # Assert it was effectively serial
    # 4 * 0.05 = 0.20s. Allow some overhead.
    # If it was parallel, it would be ~0.05s.
    assert duration >= 0.18, f"Execution was too fast ({duration}s), possibly ignored concurrency limit."


@pytest.mark.asyncio
async def test_concurrency_constraint_parallel(engine, connector):
    """
    Verify that WITHOUT constraints (or with high limit), tasks run in parallel.
    """
    @task
    async def slow_task(x: int):
        await asyncio.sleep(0.05)
        return x

    workflow = slow_task.map(x=[1, 2, 3, 4])

    # Start engine
    start = time.time()
    
    # Run without injecting constraints (defaults to unlimited/system limits)
    results = await engine.run(workflow)
    
    duration = time.time() - start

    assert sorted(results) == [1, 2, 3, 4]

    # Assert it was parallel
    # Should be close to 0.05s
    assert duration < 0.15, f"Execution was too slow ({duration}s), possibly not parallel."


@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, connector):
    """
    Verify that 'global' scope concurrency limit affects ALL tasks.
    """
    @task
    async def task_a():
        await asyncio.sleep(0.05)
        return "A"

    @task
    async def task_b():
        await asyncio.sleep(0.05)
        return "B"

    # Tasks A and B are independent, should run parallel by default
    @task
    def gather(a, b):
        return [a, b]

    workflow = gather(task_a(), task_b())

    run_task = asyncio.create_task(engine.run(workflow))
    await asyncio.sleep(0.01)

    # Inject Global Limit = 1
    constraint_payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1},
    }
    await connector.trigger("cascade/constraints/global", constraint_payload)

    start = time.time()
    await run_task
    duration = time.time() - start

    # Serial execution of A and B = ~0.10s
    assert duration >= 0.09