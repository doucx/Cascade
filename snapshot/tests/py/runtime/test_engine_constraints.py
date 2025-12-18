import asyncio
from typing import Callable, Awaitable, Dict, Any

import pytest

from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
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


class MockExecutor(Executor):
    async def execute(self, node, args, kwargs):
        # Simulate execution time to allow test control flow to inject constraints
        # while the engine is "busy" waiting for this task.
        await asyncio.sleep(0.05)
        return f"Result for {node.name}"


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=mock_connector,
    )


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


async def wait_for_task_start(spy, task_name: str, timeout: float = 2.0):
    """Helper coroutine to wait for a specific task to start."""
    from cascade.runtime.events import TaskExecutionStarted

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        started_events = spy.events_of_type(TaskExecutionStarted)
        if any(e.task_name == task_name for e in started_events):
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Timeout waiting for task '{task_name}' to start.")


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
    # The actual topic is cascade/constraints/#, our mock logic handles the match
    assert "cascade/constraints/#" in mock_connector.subscriptions
    assert callable(mock_connector.subscriptions["cascade/constraints/#"])


@pytest.mark.asyncio
async def test_engine_updates_constraints_on_message(
    engine_with_connector, mock_connector
):
    """
    Verify that the Engine's ConstraintManager is updated when a valid message is received.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Simulate receiving a constraint message
    constraint_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        "cascade/constraints/control", constraint_payload
    )

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
    
    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Payload missing the required 'id' key
    malformed_payload = {
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        "cascade/constraints/control", malformed_payload
    )

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
        solver=NativeSolver(),
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

    # 3. Wait for the first task to START.
    # We want to inject the pause while A is running (or at least before B starts).
    # Since Engine awaits tasks in a stage, injecting here ensures the constraint
    # is ready when Engine wakes up for Stage 2.
    await wait_for_task_start(spy, "task_a")

    # 4. Inject the pause command immediately
    pause_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", pause_payload)

    # 5. Wait to ensure A finishes and Engine has had time to process Stage 2 logic
    # We wait for A to finish first
    await wait_for_task_finish(spy, "task_a")
    # Then wait a bit more to allow Engine to potentially (incorrectly) start B
    await asyncio.sleep(0.2)

    # 6. Assert based on the event stream
    started_task_names = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}

    assert "task_a" in started_task_names
    assert "task_b" not in started_task_names, "task_b should have been paused"
    assert "task_c" not in started_task_names

    # 7. Cleanup
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_engine_pauses_and_resumes_specific_task(mock_connector, bus_and_spy):
    """
    End-to-end test for task-specific pause and resume functionality.
    """
    from cascade.spec.task import task
    from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished

    bus, spy = bus_and_spy
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Workflow: A -> B -> C
    @task
    def task_a():
        return "A"

    @task
    def task_b(a):
        return f"B after {a}"

    @task
    def task_c(b):
        return f"C after {b}"

    workflow = task_c(task_b(task_a()))

    # 2. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for 'task_a' to finish. This ensures the engine is ready for 'task_b'.
    await wait_for_task_finish(spy, "task_a")

    # 4. Inject a PAUSE command specifically for 'task_b'
    pause_scope = "task:task_b"
    pause_payload = {
        "id": "pause-b",
        "scope": pause_scope,
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", pause_payload
    )

    # 5. Wait briefly and assert that 'task_b' has NOT started
    await asyncio.sleep(0.2)
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "'task_b' started despite pause constraint"

    # 6. Inject a RESUME command for 'task_b'
    # An empty payload on a retained topic clears the constraint.
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", ""
    )

    # 7. Wait for the rest of the workflow to complete
    await wait_for_task_finish(spy, "task_c", timeout=1.0)

    # 8. Final assertions on the complete event stream
    finished_tasks = {
        e.task_name
        for e in spy.events_of_type(TaskExecutionFinished)
        if e.status == "Succeeded"
    }
    assert finished_tasks == {"task_a", "task_b", "task_c"}

    # 9. Verify the final result
    final_result = await run_task
    # Note: Since we use MockExecutor, the result is the fixed string it returns,
    # not the result of the actual task function.
    assert final_result == "Result for task_c"
