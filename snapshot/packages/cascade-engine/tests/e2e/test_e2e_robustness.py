import asyncio
import pytest
from unittest.mock import MagicMock, ANY

import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionStarted
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict

from .harness import InProcessConnector, ControllerTestApp


@pytest.fixture
def mock_ui_bus(monkeypatch):
    """Mocks the UI bus where it's used for constraint error logging."""
    mock_bus = MagicMock()
    # This must target where 'bus' is imported and used, which is now handlers.py
    monkeypatch.setattr("cascade.runtime.constraints.handlers.bus", mock_bus)
    return mock_bus


@pytest.mark.asyncio
async def test_engine_recovers_from_malformed_rate_limit(bus_and_spy, mock_ui_bus):
    """
    Verifies that the Engine:
    1. Does not deadlock when receiving a malformed rate_limit constraint.
    2. Logs an error via the UI bus.
    3. Continues to process valid subsequent constraints (like pause).
    """
    engine_bus, spy = bus_and_spy
    engine_connector = InProcessConnector()
    controller = ControllerTestApp(engine_connector)

    # Synchronization primitive to control workflow execution
    task_a_can_finish = asyncio.Event()

    # 1. Define a workflow that blocks until we allow it
    @cs.task
    async def task_a():
        # Signal that we have started and are now waiting
        spy.events.append("task_a_waiting")
        await task_a_can_finish.wait()
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(task_a())

    # 2. Configure and start the engine in the background
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=engine_bus,
        connector=engine_connector,
    )
    engine_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for the engine to be in a stable, blocked state inside task_a
    for _ in range(50):
        await asyncio.sleep(0.01)
        if "task_a_waiting" in spy.events:
            break
    else:
        pytest.fail("Engine did not enter the waiting state in task_a.")

    # 4. Send the MALFORMED rate limit constraint. Engine is guaranteed to be listening.
    malformed_constraint = GlobalConstraint(
        id="bad-rate-1",
        scope="global",
        type="rate_limit",
        params={"rate": "this-is-not-a-valid-rate"},
    )
    payload = asdict(malformed_constraint)
    await controller_connector.publish("cascade/constraints/global", payload)

    # 5. Assert that a UI error was logged
    await asyncio.sleep(0.02)  # Give listener loop time to process
    mock_ui_bus.error.assert_called_once_with(
        "constraint.parse.error",
        constraint_type="rate_limit",
        raw_value="this-is-not-a-valid-rate",
        error=ANY,
    )

    # 6. Send a VALID pause constraint.
    await controller.pause(scope="global")
    await asyncio.sleep(0.02)  # Allow pause to be processed

    # 7. Unblock task_a. The engine will now finish it and attempt to schedule task_b
    task_a_can_finish.set()
    await asyncio.sleep(0.02)

    # 8. Assert that task_b NEVER started because of the pause
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks

    # 9. Cleanup
    assert not engine_task.done(), "Engine should be paused, not finished."
    engine_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_task
