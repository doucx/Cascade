import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished
from cascade.connectors.mqtt import MqttConnector

from tests.py.e2e.harness import MockWorkExecutor

# NOTE: This test suite requires a live MQTT broker running on localhost:1883.
# You can start one easily with Docker:
# docker run -it --rm --name mosquitto -p 1883:1883 eclipse-mosquitto

async def run_cli_command(command: str):
    """Executes a shell command and waits for it to complete."""
    proc = await asyncio.create_subprocess_shell(command)
    await proc.wait()
    assert proc.returncode == 0, f"CLI command failed: {command}"


@pytest.mark.asyncio
@pytest.mark.system
async def test_updating_rate_limit_via_cli_is_idempotent(bus_and_spy):
    """
    A full system test verifying that using the cs-controller CLI to update
    a rate limit correctly unblocks the engine.
    This will FAIL before the idempotency fix, because the CLI generates
    two different random IDs, creating conflicting constraints.
    """
    bus, spy = bus_and_spy
    
    # This connector talks to a REAL MQTT broker
    connector = MqttConnector(hostname="localhost", port=1883)

    # ARRANGE
    @cs.task
    def fast_task(i: int):
        return i

    workflow = fast_task.map(i=range(10))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=connector,
    )

    # ACT & ASSERT
    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit.
        await run_cli_command("cs-controller set-limit --scope global --rate 1/s")

        # 2. Wait long enough for the engine to be throttled.
        # We wait up to 2s for at least one task to finish.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. In the buggy version, this adds a NEW conflicting limit.
        await run_cli_command("cs-controller set-limit --scope global --rate 100/s")

        # 4. The engine should now finish quickly. If it's deadlocked, this will time out.
        await asyncio.wait_for(engine_task, timeout=2.0)

    except asyncio.TimeoutError:
        pytest.fail(
            "Engine timed out. This likely means it got stuck on the old '1/s' "
            "rate limit due to conflicting constraints from the non-idempotent CLI."
        )
    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task
        # And clear the constraint for other tests
        await run_cli_command("cs-controller resume global")

    # Final check
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10