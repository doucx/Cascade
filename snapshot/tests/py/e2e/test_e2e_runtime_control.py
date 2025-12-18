import asyncio
import pytest
from unittest.mock import AsyncMock

import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_runtime_pause_resume_mid_stage(bus_and_spy):
    """
    Validates that the engine can be paused and resumed while a stage is in-flight.
    We use resource limits to force sequential execution of parallel tasks,
    creating a window to inject the pause command.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    first_task_started = asyncio.Event()

    @cs.task
    async def long_task(name: str):
        if name == "A":
            first_task_started.set()
            # Task A takes some time to finish, holding the resource
            await asyncio.sleep(0.1)
        return f"Done {name}"

    # Two tasks that COULD run in parallel, but will be limited by resources
    # We require 'slots=1', and system will have 'slots=1'
    task_a = long_task("A").with_constraints(slots=1)
    task_b = long_task("B").with_constraints(slots=1)

    @cs.task
    def gather(a, b):
        return [a, b]

    workflow = gather(task_a, task_b)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
        system_resources={"slots": 1} # Force serial execution
    )

    # Start the engine in the background
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # 1. Wait until the first task (A) starts
    await asyncio.wait_for(first_task_started.wait(), timeout=1)

    # 2. Issue a PAUSE command while A is running. 
    # Because B is waiting for the 'slot', it is still in the pending queue.
    await controller.pause(scope="global")
    
    # 3. Wait enough time for A to finish and release the resource.
    # Normally B would start now, but PAUSE should prevent it.
    await asyncio.sleep(0.2)

    # 4. ASSERT: Only A should have started. B should be blocked by PAUSE.
    started_events = spy.events_of_type(TaskExecutionStarted)
    # Note: Depending on timing, gather might not have started, or long_task A started.
    # We filter for 'long_task'.
    long_task_starts = [e for e in started_events if e.task_name == "long_task"]
    assert len(long_task_starts) == 1, "Task B started despite pause!"
    assert long_task_starts[0].task_id == task_a._uuid

    # 5. Issue a RESUME command
    await controller.resume(scope="global")

    # 6. ASSERT: The workflow now completes
    final_result = await asyncio.wait_for(engine_run_task, timeout=1)
    assert sorted(final_result) == ["Done A", "Done B"]

    # Verify that B eventually ran
    started_events = spy.events_of_type(TaskExecutionStarted)
    long_task_starts = [e for e in started_events if e.task_name == "long_task"]
    assert len(long_task_starts) == 2


@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition(bus_and_spy):
    """
    Validates that the connector.connect() is called before any attempt
    to publish the RunStarted event, preventing a race condition.
    """
    bus, spy = bus_and_spy

    # Mock the connector to spy on its method calls
    mock_connector = AsyncMock(spec=InProcessConnector)
    
    # Track call order
    call_order = []
    mock_connector.connect.side_effect = lambda: call_order.append("connect")
    
    original_publish = mock_connector.publish
    
    async def patched_publish(*args, **kwargs):
        call_order.append("publish")
        return await original_publish(*args, **kwargs)

    mock_connector.publish = patched_publish

    # Crucial: Must manually attach the subscriber because we are building Engine manually
    TelemetrySubscriber(bus, mock_connector)

    @cs.task
    def simple_task():
        return "ok"
    
    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=mock_connector,
    )
    
    await engine.run(workflow)

    # ASSERT
    # We expect 'connect' to be the first call to the connector
    assert call_order[0] == "connect"
    # Followed by a publish (from RunStarted event)
    assert "publish" in call_order
    
    mock_connector.connect.assert_awaited_once()
    # At least one publish should have happened (RunStarted)
    mock_connector.publish.assert_called()