好的，测试已通过！我们成功修复了底层的竞争条件和 API 误用。现在，我们进入路线图的最后阶段：为这个新功能编写专门的、全面的测试，以确保其行为符合预期，并防止未来的回归。

我将添加一个新的测试用例，它只在支持 UDS 的平台（Linux, macOS）上运行，专门用来验证 UDS 信号的**低延迟**特性。

## [WIP] feat(tests): Add specific E2E tests for SqliteConnector UDS signaling

### 用户需求
为 `SqliteConnector` 的 UDS 功能编写专门的端到端测试，以验证其正确性和低延迟性能，从而完成开发路线图的步骤 4。

### 评论
这是确保新功能健壮性的关键一步。通过为 UDS 信号机制添加一个专门的、有性能断言的测试，我们不仅能验证其功能的正确性，还能确保其核心优势——“近乎即时”的唤醒——得到了保证。这将作为一个明确的性能基准，防止未来的代码变更无意中引入延迟。

### 目标
1.  在 `test_e2e_sqlite_connector.py` 中添加一个新的测试函数 `test_uds_wakeup_is_instantaneous`。
2.  使用 `@pytest.mark.skipif(sys.platform == "win32")` 装饰器，确保此测试仅在非 Windows 平台上运行。
3.  测试逻辑将验证：当一个 `Engine` 因约束而阻塞时，一个 `resume` 命令能通过 UDS 信号将其唤醒，并且整个过程的耗时远小于一个轮询周期 (`POLL_INTERVAL`)。

### 基本原理
现有的测试验证了连接器在功能上的**正确性**（即约束最终会被应用）。这个新测试将专注于验证其在支持的平台上的**性能**。通过在一个被暂停的工作流上发布 `resume` 命令，并断言其完成时间远小于 `POLL_INTERVAL`，我们可以明确地证明 UDS 信号机制正在按预期工作，并且确实消除了轮询延迟。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/sqlite-connector #task/action/integration #task/state/end

---

### Script

#### Acts 1: 添加 UDS 专项测试并提交

我将重写整个测试文件，加入新的 UDS 测试用例。由于这是这个宏观任务（实现 SqliteConnector）的最后一步，我将同时生成 `git add` 和 `git commit` 指令，将 `connector.py` 的实现和它的测试作为一个完整的逻辑单元提交。

~~~~~act
write_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
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
~~~~~
