import asyncio
import time
import sys
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.connectors.sqlite.connector import SqliteConnector, POLL_INTERVAL


# --- Fixtures ---


@pytest.fixture
def unique_paths(tmp_path):
    """Provides unique, isolated paths for DB and UDS for each test."""
    db_path = tmp_path / "test_control.db"
    uds_path = tmp_path / "cascade_test.sock"
    return str(db_path), str(uds_path)


@pytest.fixture
def controller_connector(unique_paths):
    """Provides a connector instance to act as the 'controller' CLI."""
    db_path, uds_path = unique_paths
    return SqliteConnector(db_path=db_path, uds_path=uds_path)


@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the SqliteConnector."""
    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = SqliteConnector(db_path=db_path, uds_path=uds_path)

    class TimedMockExecutor(LocalExecutor):
        async def execute(self, node, args, kwargs):
            await asyncio.sleep(0.05)
            return await super().execute(node, args, kwargs)

    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(),
        bus=bus,
        connector=connector,
    )


# --- Test Cases ---


@pytest.mark.asyncio
async def test_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies the core pause and resume functionality, works for both UDS and polling.
    """
    _, spy = bus_and_spy
    task_a_started = asyncio.Event()

    @cs.task
    async def slow_task_a():
        task_a_started.set()
        await asyncio.sleep(POLL_INTERVAL * 2)
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(slow_task_a())

    async with controller_connector:
        engine_run_task = asyncio.create_task(engine.run(workflow))
        await asyncio.wait_for(task_a_started.wait(), timeout=1.0)

        scope = "task:task_b"
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        pause_payload = {"id": "pause-b", "scope": scope, "type": "pause", "params": {}}
        await controller_connector.publish(topic, pause_payload)

        # Wait for slow_task_a to finish.
        await asyncio.sleep(POLL_INTERVAL * 2.5)

        started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
        assert "task_b" not in started_tasks, "task_b started despite pause constraint"

        await controller_connector.publish(topic, {})

        # The workflow should now complete quickly.
        final_result = await asyncio.wait_for(engine_run_task, timeout=POLL_INTERVAL * 2)
        assert final_result == "B"

    finished_tasks = {
        e.task_name
        for e in spy.events_of_type(TaskExecutionFinished)
        if e.status == "Succeeded"
    }
    assert finished_tasks == {"slow_task_a", "task_b"}


@pytest.mark.asyncio
async def test_constraint_update_idempotency_e2e(
    engine, controller_connector, bus_and_spy
):
    """
    Tests that publishing a new constraint for the same scope correctly replaces the old one.
    """
    scope = "global"
    topic = "cascade/constraints/global"

    @cs.task
    def my_task(i):
        return i

    workflow = my_task.map(i=list(range(5)))

    async with controller_connector:
        # Set a very slow initial rate limit
        slow_limit = {
            "id": "rate-1",
            "scope": scope,
            "type": "rate_limit",
            "params": {"rate": "1/s"},
        }
        await controller_connector.publish(topic, slow_limit)

        engine_run_task = asyncio.create_task(engine.run(workflow))
        await asyncio.sleep(1.5)  # Wait for at least one task to complete

        # Now, update the limit to be very fast
        fast_limit = {
            "id": "rate-2",
            "scope": scope,
            "type": "rate_limit",
            "params": {"rate": "100/s"},
        }
        await controller_connector.publish(topic, fast_limit)

        # The rest of the tasks should complete quickly
        await asyncio.wait_for(engine_run_task, timeout=1.0)

    finished_events = spy.events_of_type(TaskExecutionFinished)
    assert len(finished_events) == 5


@pytest.mark.asyncio
async def test_constraint_ttl_expiration_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies that constraints with a TTL are automatically removed after they expire.
    """
    scope = "global"
    topic = "cascade/constraints/global"
    ttl_seconds = POLL_INTERVAL * 2.5

    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    async with controller_connector:
        expires_at = time.time() + ttl_seconds
        pause_payload = {
            "id": "pause-ttl",
            "scope": scope,
            "type": "pause",
            "params": {},
            "expires_at": expires_at,
        }
        await controller_connector.publish(topic, pause_payload)

        engine_run_task = asyncio.create_task(engine.run(workflow))
        await asyncio.sleep(POLL_INTERVAL + 0.1)
        assert not engine_run_task.done()

        await asyncio.sleep(ttl_seconds)

        final_result = await asyncio.wait_for(
            engine_run_task, timeout=POLL_INTERVAL * 2
        )
        assert final_result == "done"


@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not available on Windows")
@pytest.mark.asyncio
async def test_uds_wakeup_is_instantaneous(engine, controller_connector, bus_and_spy):
    """
    Verifies that on supported platforms, UDS signaling wakes up a paused
    engine much faster than the polling interval.
    """
    scope = "global"
    topic = "cascade/constraints/global"

    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    async with controller_connector:
        # 1. Pause the engine before it starts
        pause_payload = {"id": "pause-uds", "scope": scope, "type": "pause", "params": {}}
        await controller_connector.publish(topic, pause_payload)

        # 2. Start the engine, it should immediately block
        engine_run_task = asyncio.create_task(engine.run(workflow))
        await asyncio.sleep(0.01)  # Yield to let engine initialize and block
        assert not engine_run_task.done()

        # 3. Send resume and measure time
        start_time = time.time()
        await controller_connector.publish(topic, {})  # Resume command
        
        # 4. Wait for completion, with a timeout that is LESS than the poll interval
        await asyncio.wait_for(engine_run_task, timeout=(POLL_INTERVAL / 2))
        duration = time.time() - start_time

    # 5. Assert that wakeup was very fast
    assert duration < POLL_INTERVAL