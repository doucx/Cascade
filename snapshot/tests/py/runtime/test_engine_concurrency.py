import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List

import pytest

import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished, Event


# --- Test Fixtures and Mocks ---

class MockConnector(Connector):
    """A mock connector for testing Engine's subscription and constraint logic."""

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> None:
        pass

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        for sub_topic, callback in self.subscriptions.items():
            if sub_topic.endswith("/#") and topic.startswith(sub_topic[:-2]):
                await callback(topic, payload)

class SpySubscriber:
    """A standard test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events: List[Event] = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.fixture
def bus_and_spy_for_concurrency():
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy

@pytest.fixture
def mock_connector_for_concurrency():
    return MockConnector()

@pytest.fixture
def engine_with_connector(mock_connector_for_concurrency, bus_and_spy_for_concurrency):
    bus, _ = bus_and_spy_for_concurrency
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=mock_connector_for_concurrency,
    )

class ConcurrencyTracker:
    """Helper class to monitor concurrency levels from an event stream."""

    def __init__(self, spy: SpySubscriber):
        self._spy = spy
        self.max_concurrent = 0
        self.current_concurrent = 0
    
    def update(self):
        started = len([e for e in self._spy.events_of_type(TaskExecutionStarted) if e.task_name == "slow_task"])
        finished = len([e for e in self._spy.events_of_type(TaskExecutionFinished) if e.task_name == "slow_task"])
        self.current_concurrent = started - finished
        if self.current_concurrent > self.max_concurrent:
            self.max_concurrent = self.current_concurrent


# --- Test Case ---

@pytest.mark.asyncio
async def test_engine_respects_dynamic_concurrency_limit(
    engine_with_connector: Engine, mock_connector_for_concurrency: MockConnector, bus_and_spy_for_concurrency
):
    """
    End-to-end test verifying that a dynamically added 'concurrency' constraint
    is respected by the engine, limiting parallel execution of tasks.
    """
    bus, spy = bus_and_spy_for_concurrency
    tracker = ConcurrencyTracker(spy)

    # 1. Define a workflow with 4 slow, parallel tasks
    @cs.task
    async def slow_task(i: int):
        await asyncio.sleep(0.1)
        return i

    # All tasks can run in parallel in the first stage
    workflow = [slow_task(i) for i in range(4)]
    
    @cs.task
    def gather(results: list):
        return results

    final_target = gather(workflow)

    # 2. Start the engine in a background task
    run_task = asyncio.create_task(engine_with_connector.run(final_target))
    
    # 3. Give the engine a moment to start and subscribe to the connector
    await asyncio.sleep(0.01)

    # 4. Inject the concurrency limit command via the mock connector
    constraint_scope = "task:slow_task"
    limit = 2
    concurrency_payload = {
        "id": "limit-slow-tasks",
        "scope": constraint_scope,
        "type": "concurrency",
        "params": {"limit": limit},
    }
    await mock_connector_for_concurrency._trigger_message(
        f"cascade/constraints/{constraint_scope.replace(':', '/')}",
        concurrency_payload,
    )
    
    # 5. Monitor the execution
    start_time = time.time()
    
    while not run_task.done():
        tracker.update()
        assert tracker.current_concurrent <= limit
        await asyncio.sleep(0.01)

    duration = time.time() - start_time
    
    # 6. Final assertions
    final_result = await run_task
    assert sorted(final_result) == [0, 1, 2, 3]

    tracker.update()
    assert tracker.max_concurrent == limit
    assert duration > 0.18

    assert len([e for e in spy.events_of_type(TaskExecutionStarted) if e.task_name == "slow_task"]) == 4
    assert len([e for e in spy.events_of_type(TaskExecutionFinished) if e.task_name == "slow_task"]) == 4