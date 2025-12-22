import asyncio
import pytest
from unittest.mock import MagicMock, ANY

import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionStarted
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict

from .harness import InProcessConnector, MockWorkExecutor, ControllerTestApp


@pytest.fixture
def mock_ui_bus(monkeypatch):
    """Mocks the UI bus where it's used for constraint error logging."""
    mock_bus = MagicMock()
    # This must target where 'bus' is imported and used, which is now handlers.py
    monkeypatch.setattr("cascade.runtime.constraints.handlers.bus", mock_bus)
    return mock_bus


@pytest.mark.asyncio
async def test_engine_recovers_from_malformed_rate_limit(
    bus_and_spy, mock_ui_bus
):
    """
    Verifies that the Engine:
    1. Does not deadlock when receiving a malformed rate_limit constraint.
    2. Logs an error via the UI bus.
    3. Continues to process valid subsequent constraints (like pause).
    """
    engine_bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. Define a simple two-stage workflow
    @cs.task
    def task_a():
        return "A"

    @cs.task
    async def task_b(dep):
        # This task should never start if the pause works
        await asyncio.sleep(0.1)
        return "B"

    workflow = task_b(task_a())

    # 2. Configure and start the engine in the background
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=engine_bus,
        connector=connector,
    )
    engine_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for task_a to start, so we know the engine is active
    for _ in range(20):
        await asyncio.sleep(0.01)
        if spy.events_of_type(TaskExecutionStarted):
            break
    else:
        pytest.fail("Engine did not start task_a in time.")

    # 4. Send the MALFORMED rate limit constraint
    malformed_constraint = GlobalConstraint(
        id="bad-rate-1",
        scope="global",
        type="rate_limit",
        params={"rate": "this-is-not-a-valid-rate"},
    )
    payload = asdict(malformed_constraint)
    await connector.publish("cascade/constraints/global", payload)

    # 5. Assert that a UI error was logged
    # Give the engine a moment to process the bad message
    await asyncio.sleep(0.01)
    print(f"DEBUG: Mock calls: {mock_ui_bus.error.call_args_list}")
    mock_ui_bus.error.assert_called_once_with(
        "constraint.parse.error",
        constraint_type="rate_limit",
        raw_value="this-is-not-a-valid-rate",
        error=ANY,
    )

    # 6. Send a VALID pause constraint. If the engine is deadlocked,
    # it will never process this message.
    await controller.pause(scope="global")

    # 7. Wait for task_a to finish, then wait a bit more.
    # If the engine is responsive, it will pause and not schedule task_b.
    # If it's deadlocked, the engine_task will hang.
    await asyncio.sleep(0.2)

    # 8. Assert that task_b NEVER started, proving the pause was effective
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "task_b started, indicating the engine ignored the pause command."

    # 9. Cleanup
    assert not engine_task.done(), "Engine task finished, it should be paused."
    engine_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_task