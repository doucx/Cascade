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

    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            hostname="localhost",  # Constant for test purposes
            port=1883,           # Constant for test purposes
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    # This single connector instance is shared between the Engine and the Controller logic.
    connector = InProcessConnector()

    # 1. Intercept any creation of MqttConnector to return our shared instance.
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: connector
    )

    # 2. Neuter connect/disconnect calls from the controller's logic to prevent
    #    it from closing the connection that the Engine relies on.
    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr(controller_app.MqttConnector, "connect", noop)
    monkeypatch.setattr(controller_app.MqttConnector, "disconnect", noop)

    return InProcessController(connector)

# --- The Failing Test Case ---

@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(controller_runner, bus_and_spy):
    """
    This test is EXPECTED TO FAIL with a timeout on the pre-fix codebase.
    It verifies that a non-idempotent CLI controller creates conflicting
    constraints that deadlock the engine. After the fix is applied, this
    test should pass.
    """
    bus, spy = bus_and_spy
    
    @cs.task
    def fast_task(i: int):
        return i
    workflow = fast_task.map(i=range(10))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit.
        await controller_runner.set_limit(scope="global", rate="1/s")

        # 2. Wait to confirm the engine is throttled.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. The bug causes this to ADD a new conflicting constraint.
        await controller_runner.set_limit(scope="global", rate="100/s")

        # 4. The engine should now finish quickly. The bug will cause a timeout here.
        await asyncio.wait_for(engine_task, timeout=2.0)

    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task

    # This part is only reached if the test passes (i.e., after the bug is fixed).
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10