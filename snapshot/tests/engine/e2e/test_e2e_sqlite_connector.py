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
def controller_connector(sqlite_db_path, event_loop):
    """
    Provides a connector instance to act as the 'controller' CLI.
    This is a sync fixture that manages an async resource.
    """
    connector = SqliteConnector(db_path=str(sqlite_db_path))
    event_loop.run_until_complete(connector.connect())
    yield connector
    event_loop.run_until_complete(connector.disconnect())


@pytest.fixture
def engine(sqlite_db_path, bus_and_spy):
    """Provides a fully configured Engine using the SqliteConnector."""
    bus, _ = bus_and_spy
    connector = SqliteConnector(db_path=str(sqlite_db_path))
    
    # We need a mock executor that takes a bit of time to run
    # so we can inject constraints during its execution.
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
    """
    _, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(task_a())

    # Start the engine in the background
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # Wait for task_a to finish, so we are sure the engine is at the point
    # of deciding whether to run task_b.
    await asyncio.sleep(POLL_INTERVAL + 0.1) 

    # Publish a pause for task_b
    scope = "task:task_b"
    topic = f"cascade/constraints/{scope.replace(':', '/')}"
    pause_payload = {
        "id": "pause-b", "scope": scope, "type": "pause", "params": {}
    }
    await controller_connector.publish(topic, pause_payload)

    # Wait for the poll interval to pass, engine should pick up the pause
    await asyncio.sleep(POLL_INTERVAL + 0.1)

    # Assert that task_b has NOT started
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks

    # Now, publish a resume command (empty payload)
    await controller_connector.publish(topic, {})

    # Wait for the poll interval again for resume to be picked up
    await asyncio.sleep(POLL_INTERVAL + 0.1)

    # The workflow should now complete
    final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
    assert final_result == "B"

    finished_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionFinished) if e.status == "Succeeded"}
    assert finished_tasks == {"task_a", "task_b"}


@pytest.mark.asyncio
async def test_constraint_update_idempotency_e2e(engine, controller_connector, bus_and_spy):
    """
    Tests that publishing a new constraint for the same scope correctly replaces
    the old one (UPSERT behavior).
    """
    scope = "global"
    topic = "cascade/constraints/global"

    @cs.task
    def my_task(i):
        return i

    # A workflow of 5 independent tasks
    workflow = my_task.map(i=list(range(5)))

    # Set a very slow initial rate limit
    slow_limit = {
        "id": "rate-1", "scope": scope, "type": "rate_limit", "params": {"rate": f"1/{POLL_INTERVAL * 4}"} # 1 task per 4 polls
    }
    await controller_connector.publish(topic, slow_limit)
    
    start_time = time.time()
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # Wait for at least one task to complete under the slow limit
    await asyncio.sleep(POLL_INTERVAL * 5)

    # Now, update the limit to be very fast
    fast_limit = {
        "id": "rate-2", "scope": scope, "type": "rate_limit", "params": {"rate": "100/s"}
    }
    await controller_connector.publish(topic, fast_limit)

    # The rest of the tasks should complete quickly
    await asyncio.wait_for(engine_run_task, timeout=2.0)
    duration = time.time() - start_time

    # 5 tasks * ~0.8s/task (slow) would be ~4s.
    # 1 task slow (~0.8s) + 4 tasks fast (<0.1s) should be well under 2s.
    assert duration < 2.0


@pytest.mark.asyncio
async def test_constraint_ttl_expiration_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies that constraints with a TTL are automatically removed after they expire.
    """
    scope = "global"
    topic = "cascade/constraints/global"
    ttl_seconds = POLL_INTERVAL * 2.5 # Make it expire after a couple of polls

    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

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

    # The engine's internal cleanup should detect the expired constraint on its
    # next wakeup and resume execution.
    final_result = await asyncio.wait_for(engine_run_task, timeout=POLL_INTERVAL * 2)
    assert final_result == "done"