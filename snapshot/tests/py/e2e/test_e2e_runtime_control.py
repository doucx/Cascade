import asyncio
import pytest
from unittest.mock import AsyncMock, patch

import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_runtime_pause_resume_mid_stage(bus_and_spy):
    """
    Validates that the engine can be paused and resumed while a stage is in-flight.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    first_task_started = asyncio.Event()
    second_task_can_start = asyncio.Event()

    @cs.task
    async def long_task(name: str):
        if name == "A":
            first_task_started.set()
            await second_task_can_start.wait()
        await asyncio.sleep(0.01) # Simulate work
        return f"Done {name}"

    # Two tasks that can run in parallel
    task_a = long_task("A")
    task_b = long_task("B")

    @cs.task
    def gather(a, b):
        return [a, b]

    workflow = gather(task_a, task_b)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )

    # Start the engine in the background
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # 1. Wait until the first task has definitively started
    await asyncio.wait_for(first_task_started.wait(), timeout=1)

    # 2. Immediately issue a PAUSE command
    await controller.pause(scope="global")
    
    # 3. Allow the first task to finish its long wait
    second_task_can_start.set()
    await asyncio.sleep(0.05) # Give scheduler time to react

    # 4. ASSERT: The engine is paused, so task B should not have started
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 1
    assert started_events[0].task_name == "long_task"

    # 5. Issue a RESUME command
    await controller.resume(scope="global")

    # 6. ASSERT: The workflow now completes
    final_result = await asyncio.wait_for(engine_run_task, timeout=1)
    assert sorted(final_result) == ["Done A", "Done B"]

    # Verify that the second task eventually ran
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 3 # gather, long_task, long_task


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
    
    # We must patch the publish method on the *instance* after it's created,
    # because TelemetrySubscriber gets a reference to the bound method.
    # So we use a wrapper for the subscriber instead.
    
    original_publish = mock_connector.publish
    
    async def patched_publish(*args, **kwargs):
        call_order.append("publish")
        return await original_publish(*args, **kwargs)

    mock_connector.publish = patched_publish

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
    mock_connector.subscribe.assert_awaited_once_with(
        "cascade/constraints/#", engine._on_constraint_update
    )
    # At least one publish should have happened (RunStarted)
    mock_connector.publish.assert_called()