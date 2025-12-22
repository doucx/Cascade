import asyncio
import time
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.connectors.sqlite.connector import SqliteConnector, POLL_INTERVAL


# --- Fixtures ---

@pytest.fixture
def sqlite_db_path(tmp_path):
    """Provides a unique, isolated SQLite database path for each test."""
    return tmp_path / "test_control.db"


@pytest.fixture
def controller_connector(sqlite_db_path):
    """Provides a connector instance to act as the 'controller' CLI."""
    return SqliteConnector(db_path=str(sqlite_db_path))


@pytest.fixture
def engine(sqlite_db_path, bus_and_spy):
    """Provides a fully configured Engine using the SqliteConnector."""
    bus, _ = bus_and_spy
    connector = SqliteConnector(db_path=str(sqlite_db_path))
    
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
async def test_polling_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies the core polling loop for pause and resume functionality.
    This version fixes a race condition in the test logic.
    """
    _, spy = bus_and_spy
    task_a_started = asyncio.Event()

    @cs.task
    async def slow_task_a():
        task_a_started.set()
        # Sleep long enough for the test to publish a constraint and for a poll cycle to run
        await asyncio.sleep(POLL_INTERVAL * 2)
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(slow_task_a())

    async with controller_connector:
        # Start the engine in the background
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # 1. Wait for the slow task to start executing
        await asyncio.wait_for(task_a_started.wait(), timeout=1.0)

        # 2. While task_a is running, publish a pause for task_b
        scope = "task:task_b"
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        pause_payload = {
            "id": "pause-b", "scope": scope, "type": "pause", "params": {}
        }
        await controller_connector.publish(topic, pause_payload)

        # 3. Wait for slow_task_a to finish. During this time, the polling
        #    task in the engine MUST have run and picked up the pause constraint.
        #    We let slow_task_a finish its sleep.
        await asyncio.sleep(POLL_INTERVAL * 2 + 0.1)
        
        # 4. Assert that task_b has NOT started
        started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
        assert "task_b" not in started_tasks, "task_b started despite pause constraint"

        # 5. Now, publish a resume command
        await controller_connector.publish(topic, {})

        # 6. Wait for the next poll interval for the resume to be picked up
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # 7. The workflow should now complete
        final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
        assert final_result == "B"

    finished_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionFinished) if e.status == "Succeeded"}
    assert finished_tasks == {"slow_task_a", "task_b"}


@pytest.mark.asyncio
async def test_constraint_update_idempotency_e2e(engine, controller_connector, bus_and_spy):
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
            "id": "rate-1", "scope": scope, "type": "rate_limit", "params": {"rate": f"1/{POLL_INTERVAL * 4}"}
        }
        await controller_connector.publish(topic, slow_limit)
        
        start_time = time.time()
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # Wait for at least one task to complete
        await asyncio.sleep(POLL_INTERVAL * 5)

        # Now, update the limit to be very fast
        fast_limit = {
            "id": "rate-2", "scope": scope, "type": "rate_limit", "params": {"rate": "100/s"}
        }
        await controller_connector.publish(topic, fast_limit)

        # The rest of the tasks should complete quickly
        await asyncio.wait_for(engine_run_task, timeout=2.0)
        duration = time.time() - start_time

    assert duration < 2.0


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
        # Publish a pause constraint that expires in the near future
        expires_at = time.time() + ttl_seconds
        pause_payload = {
            "id": "pause-ttl", "scope": scope, "type": "pause", "params": {}, "expires_at": expires_at
        }
        await controller_connector.publish(topic, pause_payload)

        engine_run_task = asyncio.create_task(engine.run(workflow))

        # Wait for a poll, task should be blocked
        await asyncio.sleep(POLL_INTERVAL + 0.1)
        assert not engine_run_task.done()

        # Wait for the TTL to expire
        await asyncio.sleep(ttl_seconds)

        # The engine's internal cleanup should resume execution.
        final_result = await asyncio.wait_for(engine_run_task, timeout=POLL_INTERVAL * 2)
        assert final_result == "done"