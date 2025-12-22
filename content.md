您是对的，我的上一个修复引入了新的错误。非常感谢您提供详细的错误回溯，这清楚地指出了问题的根源。

我将立即生成一个计划来纠正这个问题。

## [WIP] fix(test): 重构 SqliteConnector 测试以正确处理异步生命周期

### 错误分析
测试再次在设置阶段失败，但这次的原因不同且更为根本：`fixture 'event_loop' not found`。

我的上一个修复方案是基于一个错误的假设：即 `pytest-asyncio` 插件总会提供一个名为 `event_loop` 的 fixture。然而，测试环境的输出明确指出，这个 fixture **不可用**。这通常意味着项目的 `pytest` 配置（可能在 `pytest.ini` 或 `pyproject.toml` 中）使用了 `asyncio_mode = auto` 或其他自定义设置，在这种模式下 `event_loop` fixture 不会被暴露出来。

因此，我之前将 `controller_connector` fixture 转换为同步函数并试图注入 `event_loop` 的尝试是行不通的。我们必须采用一种不依赖于这个特定 fixture 的模式。

### 用户需求
修复 `test_e2e_sqlite_connector.py` 中由 `fixture 'event_loop' not found` 引起的测试设置错误，并确保测试能够正确运行。

### 评论
这个错误暴露了依赖特定 `pytest` 插件内部实现（如 `event_loop` fixture）的脆弱性。最健壮、最不易出错的模式是将异步资源的生命周期管理（`connect`/`disconnect`）从 fixture 的 `yield` 语句中移出，转而在测试函数内部显式处理。

为了避免在每个测试用例中重复编写 `try...finally` 块，我们可以采用一个优雅的 Python 模式：
1.  创建一个**同步 fixture**，它只负责实例化 `SqliteConnector` 对象，不执行任何 `await` 操作。
2.  在测试函数内部，使用 `async with` 语句和一个小型的异步上下文管理器来包装这个 connector 实例，从而管理其连接的建立和拆卸。

由于 `SqliteConnector` 本身没有实现 `__aenter__` 和 `__aexit__`，我们可以使用 `contextlib.asynccontextmanager` 来轻松地创建一个临时的上下文管理器。

然而，为了保持测试代码的简洁性，最直接的方法是修改 `SqliteConnector`，使其自身成为一个异步上下文管理器。这使得测试代码既干净又直观，完全符合 Python 的最佳实践。

### 目标
1.  **增强 `SqliteConnector`**: 在 `SqliteConnector` 类中实现 `__aenter__` 和 `__aexit__` 方法，使其能够被用于 `async with` 语句。`__aenter__` 将调用 `self.connect()`，而 `__aexit__` 将调用 `self.disconnect()`。
2.  **简化 Test Fixture**: 将 `controller_connector` fixture 改为一个简单的同步函数，它只返回一个 `SqliteConnector` 的实例。
3.  **重构测试用例**: 修改所有测试用例，使用 `async with` 语句来管理 `controller_connector` 的生命周期。

### 基本原理
本计划将采用两个 `patch_file` 操作。

第一个操作将为 `SqliteConnector` 添加上下文管理器协议的支持。这是一个向后兼容的增强，因为它不改变任何现有方法的行为。

第二个操作将重构整个测试文件。通过使用 `async with`，我们不再需要 `pytest` 去处理复杂的异步生成器 fixture，从而彻底绕开了最初的 `PytestRemovedIn9Warning` 和后续的 `fixture not found` 错误。这种模式更加清晰、明确，并且完全不依赖于 `pytest-asyncio` 插件的内部实现细节。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/connector-sqlite #concept/tooling #scope/dx #ai/refine #task/domain/testing #task/object/async-fixture #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 使 `SqliteConnector` 支持异步上下文管理

我们将 `__aenter__` 和 `__aexit__` 方法添加到 `SqliteConnector` 类中，使其可以与 `async with` 配合使用。

~~~~~act
patch_file
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
~~~~~
~~~~~python
        self._conn = await asyncio.to_thread(_connect_and_setup)
        self._is_connected = True
        self._last_check_ts = time.time()

    async def disconnect(self) -> None:
~~~~~
~~~~~python
        self._conn = await asyncio.to_thread(_connect_and_setup)
        self._is_connected = True
        self._last_check_ts = time.time()
        return self

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def disconnect(self) -> None:
~~~~~

#### Acts 2: 重构测试以使用 `async with`

现在，我们重写测试文件。`controller_connector` fixture 变得非常简单，而测试用例则使用 `async with` 来清晰地管理连接的生命周期。

~~~~~act
write_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
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
    """
    _, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(task_a())

    async with controller_connector:
        # Start the engine in the background
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # Wait for task_a to finish
        await asyncio.sleep(POLL_INTERVAL + 0.1) 

        # Publish a pause for task_b
        scope = "task:task_b"
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        pause_payload = {
            "id": "pause-b", "scope": scope, "type": "pause", "params": {}
        }
        await controller_connector.publish(topic, pause_payload)

        # Wait for the poll interval to pass
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # Assert that task_b has NOT started
        started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
        assert "task_b" not in started_tasks

        # Now, publish a resume command
        await controller_connector.publish(topic, {})

        # Wait for the poll interval again
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # The workflow should now complete
        final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
        assert final_result == "B"

    finished_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionFinished) if e.status == "Succeeded"}
    assert finished_tasks == {"task_a", "task_b"}


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
~~~~~
