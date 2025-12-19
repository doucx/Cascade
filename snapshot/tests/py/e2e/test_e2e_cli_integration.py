import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished

# 导入 app 模块中的核心异步逻辑函数
from cascade.cli.controller import app as controller_app
from cascade.connectors.mqtt import MqttConnector

from .harness import InProcessConnector, MockWorkExecutor

# --- Test Harness for In-Process CLI Interaction ---

class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""
    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(self, **kwargs):
        # Directly call the async logic, bypassing Typer and asyncio.run()
        await controller_app._publish_limit(
            hostname="localhost", port=1883, **kwargs
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    # 1. Create the deterministic, in-memory connector for this test
    connector = InProcessConnector()

    # 2. Monkeypatch the MqttConnector class *where it's used* in the controller app module
    #    to always return our in-memory instance.
    #    Note: We patch the class constructor to return our instance.
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: connector
    )
    
    # 3. Return a controller instance that uses this connector
    return InProcessController(connector)

# --- The Failing Test Case ---

@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(controller_runner, bus_and_spy):
    """
    This test should FAIL with the current code due to a timeout.
    It verifies that a non-idempotent CLI controller creates conflicting
    constraints that deadlock the engine.
    """
    bus, spy = bus_and_spy
    
    # ARRANGE: Define a simple workflow
    @cs.task
    def fast_task(i: int):
        return i

    workflow = fast_task.map(i=range(10))

    # ARRANGE: Setup the engine to use the same in-memory connector
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    # ACT & ASSERT
    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit using the in-process controller.
        await controller_runner.set_limit(scope="global", rate="1/s")

        # 2. Wait long enough to confirm the engine is running but throttled.
        # We wait up to 2s for at least one task to finish.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. In the buggy version, this adds a NEW conflicting limit
        # because the CLI generates a new random ID for the constraint.
        await controller_runner.set_limit(scope="global", rate="100/s")

        # 4. The engine should now finish quickly.
        # With the bug, it will be deadlocked on the old "1/s" limit and this will time out.
        await asyncio.wait_for(engine_task, timeout=2.0)

    except asyncio.TimeoutError:
        pytest.fail(
            "Engine timed out as expected. This confirms the non-idempotent "
            "controller created conflicting constraints, deadlocking the engine."
        )
    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task

    # This part should only be reached after the bug is fixed.
    # For now, the test is expected to fail before this.
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10