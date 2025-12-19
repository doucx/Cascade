import asyncio
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_startup_pause_and_resume_e2e(bus_and_spy):
    """
    Definitive regression test for the startup race condition.
    Ensures a pre-existing 'pause' constraint is respected upon engine start,
    and that a subsequent 'resume' command unblocks execution.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. ARRANGE: Controller issues a PAUSE command *before* the engine starts.
    # This creates a retained message on the virtual broker.
    await controller.pause(scope="global")

    # 2. DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    # 3. ACT: Start the engine.
    # It should connect, subscribe, immediately receive the retained pause message,
    # and block before executing any tasks.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # 4. ASSERT: The engine is paused.
    # Yield control to allow engine to initialize and process the retained pause message.
    # With deterministic connector, this should be instant.
    await asyncio.sleep(0)
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 0, (
        "Task started execution despite global pause constraint"
    )

    # 5. ACT: Controller issues a RESUME command.
    await controller.resume(scope="global")

    # 6. ASSERT: The engine unpauses and completes the workflow.
    # The run task should now complete without timing out.
    final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
    assert final_result == "done"

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 1
    assert started_events[0].task_name == "my_task"


@pytest.mark.asyncio
async def test_startup_pause_is_respected(bus_and_spy):
    """
    A more precise regression test for the startup race condition.
    Verifies ONLY that a pre-existing 'pause' is respected.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # ARRANGE: A global pause constraint exists *before* the engine is created.
    await controller.pause(scope="global")

    # DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"
    workflow = my_task()

    # ACT: Create and start the engine.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # ASSERT: After giving the engine a moment to process initial messages,
    # no tasks should have started.
    await asyncio.sleep(0.01)  # A small sleep to let the loop run and fail

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 0, (
        "Task started execution despite global pause constraint"
    )

    # Cleanup the background task to avoid warnings
    engine_run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_run_task
