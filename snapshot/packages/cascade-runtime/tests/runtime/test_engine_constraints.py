import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional

import pytest

from cascade.graph.model import Node
from cascade.interfaces.protocols import Connector, Solver, Executor
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.spec.constraint import GlobalConstraint


# --- Test Fixtures and Mocks ---

class MockConnector(Connector):
    """A mock connector for testing Engine's subscription logic."""

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self.connected = False
        self.disconnected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        pass  # Not needed for this test

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        # Check all subscriptions for a match
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


class MockSolver(Solver):
    def resolve(self, graph):
        # Return a single stage with all non-param nodes
        return [[n for n in graph.nodes if n.node_type != "param"]]


class MockExecutor(Executor):
    async def execute(self, node, args, kwargs):
        return f"Result for {node.name}"


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=MockSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=mock_connector,
    )


# --- Test Cases ---

@pytest.mark.asyncio
async def test_engine_subscribes_to_constraints(engine_with_connector, mock_connector):
    """
    Verify that the Engine subscribes to the correct topic upon starting a run.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    await engine_with_connector.run(dummy_task())

    # Assert that subscribe was called with the correct topic
    assert "cascade/constraints/#" in mock_connector.subscriptions
    assert callable(mock_connector.subscriptions["cascade/constraints/#"])


@pytest.mark.asyncio
async def test_engine_updates_constraints_on_message(engine_with_connector, mock_connector):
    """
    Verify that the Engine's ConstraintManager is updated when a valid message is received.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Give the engine a moment to start and subscribe
    await asyncio.sleep(0.01)

    # Simulate receiving a constraint message
    constraint_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", constraint_payload)

    # Check the internal state of the ConstraintManager
    constraint_manager = engine_with_connector.constraint_manager
    stored_constraint = constraint_manager._constraints.get("global-pause")

    assert stored_constraint is not None
    assert isinstance(stored_constraint, GlobalConstraint)
    assert stored_constraint.id == "global-pause"
    assert stored_constraint.scope == "global"
    assert stored_constraint.type == "pause"

    # Allow the run to complete
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_engine_pauses_on_global_pause_constraint(mock_connector, bus_and_spy):
    """
    End-to-end test verifying the global pause functionality.
    It checks that after a pause command is received, no new tasks are started.
    """
    from cascade.spec.task import task
    from cascade.runtime.events import TaskExecutionStarted

    bus, spy = bus_and_spy
    engine = Engine(
        solver=MockSolver(),
        executor=MockExecutor(),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Define a declarative workflow
    @task
    def task_a():
        return "A"

    @task
    def task_b(a):
        return f"B after {a}"

    @task
    def task_c(b):
        return f"C after {b}"

    workflow = task_c(b=task_b(a=task_a()))

    # 2. Start the engine in a concurrent task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for the first task to complete
    await wait_for_task_finish(spy, "task_a")

    # 4. Inject the pause command
    pause_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", pause_payload)

    # 5. Wait a moment to see if the engine schedules the next task
    await asyncio.sleep(0.2)  # Longer than engine's internal sleep

    # 6. Assert based on the event stream
    started_task_names = {
        e.task_name for e in spy.events_of_type(TaskExecutionStarted)
    }

    assert "task_a" in started_task_names
    assert "task_b" not in started_task_names, "task_b should have been paused"
    assert "task_c" not in started_task_names

    # 7. Cleanup
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


async def wait_for_task_finish(spy, task_name: str, timeout: float = 2.0):
    """Helper coroutine to wait for a specific task to finish."""
    from cascade.runtime.events import TaskExecutionFinished

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        finished_events = spy.events_of_type(TaskExecutionFinished)
        if any(e.task_name == task_name for e in finished_events):
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Timeout waiting for task '{task_name}' to finish.")


@pytest.mark.asyncio
async def test_engine_handles_malformed_constraint_payload(
    engine_with_connector, mock_connector, capsys
):
    """
    Verify that the Engine logs an error but does not crash on a malformed payload.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))
    await asyncio.sleep(0.01)

    # Payload missing the required 'id' key
    malformed_payload = {
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", malformed_payload)

    # The engine should not have crashed.
    # We can check stderr for the error message.
    captured = capsys.readouterr()
    assert "[Engine] Error processing constraint" in captured.err
    assert "'id'" in captured.err  # Specifically mentions the missing key

    # Assert that no constraint was added
    assert not engine_with_connector.constraint_manager._constraints

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass