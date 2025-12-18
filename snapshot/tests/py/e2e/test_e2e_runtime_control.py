import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_runtime_pause_resume_mid_workflow(bus_and_spy):
    """
    Validates that the engine can be paused between two dependent tasks.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    task_a_finished = asyncio.Event()

    @cs.task
    async def task_a():
        await asyncio.sleep(0.01)
        return "A"

    @cs.task
    async def task_b(val):
        await asyncio.sleep(0.01)
        return f"{val}-B"

    workflow = task_b(task_a())

    # Create a custom spy to signal when task_a is finished
    def event_handler(event):
        if isinstance(event, TaskExecutionFinished) and event.task_name == "task_a":
            task_a_finished.set()

    spy.collect = event_handler
    bus.subscribe(TaskExecutionFinished, event_handler)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # 1. Wait until Task A is completely finished
    await asyncio.wait_for(task_a_finished.wait(), timeout=1)

    # 2. Immediately issue a PAUSE command. This happens before task_b is scheduled.
    await controller.pause(scope="global")
    await asyncio.sleep(0.1)  # Give scheduler time to (not) run task_b

    # 3. ASSERT: Engine is paused, task_b has not started
    # We expect only task_a to have started.
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 1
    assert started_events[0].task_name == "task_a"

    # 4. Issue RESUME
    await controller.resume(scope="global")

    # 5. ASSERT: Workflow now completes
    final_result = await asyncio.wait_for(engine_run_task, timeout=1)
    assert final_result == "A-B"

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 2  # Both tasks should have started now
    assert {ev.task_name for ev in started_events} == {"task_a", "task_b"}


@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition():
    """
    Validates that connector.connect() is called before any attempt
    to publish, by ensuring TelemetrySubscriber is correctly wired.
    """
    # Create a mock bus for events
    event_bus = cs.runtime.MessageBus()
    mock_connector = AsyncMock(spec=InProcessConnector)

    call_order = []
    # Use side_effect to track calls
    mock_connector.connect.side_effect = lambda: call_order.append("connect")
    
    # We have to patch the publish method to track calls, as it's fire-and-forget
    original_publish = mock_connector.publish
    async def patched_publish(*args, **kwargs):
        call_order.append("publish")
        return await original_publish(*args, **kwargs)
    mock_connector.publish = patched_publish

    # CRITICAL: Manually assemble the TelemetrySubscriber, as cs.run() would.
    TelemetrySubscriber(event_bus, mock_connector)

    @cs.task
    def simple_task():
        return "ok"
    
    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus, # Pass the bus with the subscriber attached
        connector=mock_connector,
    )
    
    await engine.run(workflow)

    # ASSERT
    assert len(call_order) > 0, "Connector methods were not called"
    assert call_order[0] == "connect", "connect() was not the first call"
    assert "publish" in call_order, "publish() was never called"
    
    mock_connector.connect.assert_awaited_once()
    mock_connector.subscribe.assert_awaited_once_with(
        "cascade/constraints/#", engine._on_constraint_update
    )
    mock_connector.publish.assert_called()
