好的，我理解了。之前的修复没能解决问题，这说明问题比想象的更深。在没有明确线索的情况下，盲目修改是低效的。你要求加入日志来观察内部状态，这是一个完全正确且专业的调试思路。

我怀疑问题可能出在 `_sync_and_notify` 的差分逻辑，或者在测试环境中存在某种状态污染。通过添加详细的日志，我们可以精确地追踪约束的发布、接收和处理流程。

## [WIP] fix(connector): Add diagnostic logging to SqliteConnector

### 错误分析
尽管我们修复了 `subscribe` 方法中的明显竞争条件，但测试仍然失败。这表明存在一个更微妙的问题。当前的黑盒行为使得我们无法判断故障点：
1.  **发布失败？** `publish` 方法是否成功将数据写入了数据库并发送了 UDS 信号？
2.  **信号丢失？** UDS 监听器是否真的收到了信号？
3.  **差分逻辑错误？** `_sync_and_notify` 方法在唤醒后，其内部的差分逻辑是否正确识别出了变更？
4.  **回调失败？** 变更被识别后，回调（`Engine._on_constraint_update`）是否被成功调用？

为了回答这些问题，我将在 `SqliteConnector` 的关键路径上插入详细的诊断日志。

此外，我发现了一个潜在的测试污染源：**硬编码的 UDS 路径** (`/tmp/cascade.sock`)。如果多个测试并行运行，或者一个测试异常退出未能清理 socket 文件，后续测试可能会绑定失败或连接到错误的 socket。我将修改构造函数，使其接受一个可配置的 UDS 路径，并更新测试装置以提供唯一的路径，就像我们为数据库所做的那样。

### 用户需求
为 `SqliteConnector` 添加详细的日志记录，以诊断 `e2e` 测试持续失败的根本原因，并解决潜在的 UDS 路径冲突问题。

### 评论
这是一个经典的调试场景。当直接修复无效时，最好的方法就是增强系统的可观测性。通过日志，我们将把隐性的状态变化变为显性的事件流，从而定位到问题的根源。同时修复硬编码的 UDS 路径，是提高测试健壮性的最佳实践。

### 目标
1.  修改 `SqliteConnector`，使其在构造函数中接受一个可选的 `uds_path`。
2.  在 `publish`, `_uds_listener_loop`, `_sync_and_notify` 等关键方法中添加 `print` 语句，将内部状态输出到 `stderr`。
3.  修改 `tests/engine/e2e/test_e2e_sqlite_connector.py` 中的测试装置，为每个 `SqliteConnector` 实例提供唯一的 UDS 路径。

### 基本原理
我们将利用 `pytest` 的 `capsys` 或 `caplog` 装置（虽然这里直接 `print` 到 `stderr` 也能被 pytest 捕获）来观察连接器的内部行为。每个日志条目都会带上明确的前缀（如 `[SQL-CONN-PUBLISH]`），以便我们能清晰地追踪事件的顺序和每个方法的状态。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/sqlite-connector #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 为 SqliteConnector 添加日志并修复 UDS 路径

我将重写 `connector.py` 以注入日志记录和新的 `uds_path` 参数。

~~~~~act
write_file
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
~~~~~
~~~~~python
import asyncio
import json
import sqlite3
import time
import sys
import socket
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle

POLL_INTERVAL = 0.2  # seconds
DEFAULT_UDS_PATH = "/tmp/cascade.sock"


def log(msg: str):
    """Helper for logging to stderr for test visibility."""
    print(msg, file=sys.stderr)


class UDSServerProtocol(asyncio.DatagramProtocol):
    """Protocol that sets an event when a datagram is received."""

    def __init__(self, on_recv: asyncio.Event):
        self.on_recv = on_recv

    def datagram_received(self, data, addr):
        log("[SQL-CONN-UDS] Datagram received, setting event.")
        if not self.on_recv.is_set():
            self.on_recv.set()


class _SqliteSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "SqliteConnector", task: asyncio.Task):
        self._parent = parent
        self._task = task

    async def unsubscribe(self) -> None:
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        if self._task in self._parent._background_tasks:
            self._parent._background_tasks.remove(self._task)
        if not self._parent._use_polling:
            try:
                Path(self._parent.uds_path).unlink(missing_ok=True)
            except OSError:
                pass


class SqliteConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
        uds_path: str = DEFAULT_UDS_PATH,
    ):
        self.db_path = Path(db_path).expanduser()
        self.uds_path = uds_path
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._background_tasks: List[asyncio.Task] = []
        self._last_known_constraints: Dict[str, Dict[str, Any]] = {}
        self._use_polling = sys.platform == "win32"
        self._uds_recv_event = asyncio.Event()

    async def connect(self) -> None:
        def _connect_and_setup():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS constraints (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS scope_idx ON constraints (scope)"
            )
            conn.commit()
            return conn

        self._conn = await asyncio.to_thread(_connect_and_setup)
        self._is_connected = True
        log(f"[SQL-CONN] Connected. DB: {self.db_path}, UDS: {self.uds_path}")
        return self

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def disconnect(self) -> None:
        self._is_connected = False
        if self._background_tasks:
            for task in self._background_tasks:
                task.cancel()
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
        log("[SQL-CONN] Disconnected.")

    def _topic_to_scope(self, topic: str) -> str:
        parts = topic.split("/")
        if len(parts) > 2 and parts[0:2] == ["cascade", "constraints"]:
            return ":".join(parts[2:])
        return topic

    def _scope_to_topic(self, scope: str) -> str:
        return f"cascade/constraints/{scope.replace(':', '/')}"

    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")
        scope = self._topic_to_scope(topic)
        log(f"[SQL-CONN-PUBLISH] Writing to DB for scope '{scope}': {payload.get('id', 'DELETE')}")

        def _blocking_publish():
            cursor = self._conn.cursor()
            if not payload:
                cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
            else:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["scope"],
                        payload["type"],
                        json.dumps(payload["params"]),
                        payload.get("expires_at"),
                        time.time(),
                    ),
                )
            self._conn.commit()

        await asyncio.to_thread(_blocking_publish)
        log(f"[SQL-CONN-PUBLISH] DB write complete for {payload.get('id', 'DELETE')}")

        if not self._use_polling:
            await self._send_uds_signal()

    async def _send_uds_signal(self):
        log(f"[SQL-CONN-PUBLISH] Sending UDS signal to {self.uds_path}")
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.sendto(b"\x01", self.uds_path)
            log("[SQL-CONN-PUBLISH] UDS signal sent.")
        except (ConnectionRefusedError, FileNotFoundError):
            log("[SQL-CONN-PUBLISH] UDS signal failed: No listener.")
        except Exception as e:
            log(f"[SQL-CONN-PUBLISH] UDS signal error: {e}")
        finally:
            if sock:
                sock.close()

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")
        log(f"[SQL-CONN-SUBSCRIBE] Starting subscription for topic '{topic}'")
        ready_event = asyncio.Event()

        if self._use_polling:
            task = asyncio.create_task(self._poll_for_changes(callback))
            ready_event.set()
        else:
            task = asyncio.create_task(self._uds_listener_loop(callback, ready_event))
        self._background_tasks.append(task)
        log("[SQL-CONN-SUBSCRIBE] Waiting for listener to be ready...")
        await ready_event.wait()
        log("[SQL-CONN-SUBSCRIBE] Listener is ready. Performing initial sync.")
        await self._sync_and_notify(callback)
        log("[SQL-CONN-SUBSCRIBE] Subscription complete and synced.")
        return _SqliteSubscriptionHandle(self, task)

    async def _sync_and_notify(self, callback: Callable):
        log("[SQL-CONN-SYNC] Starting sync...")
        def _blocking_fetch_all():
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM constraints")
            return cursor.fetchall()

        rows = await asyncio.to_thread(_blocking_fetch_all)
        log(f"[SQL-CONN-SYNC] Fetched {len(rows)} rows from DB.")

        current_constraints: Dict[str, Dict] = {dict(r)["id"]: dict(r) for r in rows}
        log(f"[SQL-CONN-SYNC] Current DB state keys: {list(current_constraints.keys())}")
        log(f"[SQL-CONN-SYNC] Last known state keys: {list(self._last_known_constraints.keys())}")

        # --- Diff Logic ---
        # 1. Find new and updated constraints
        for cid, current in current_constraints.items():
            last = self._last_known_constraints.get(cid)
            if not last or last["updated_at"] < current["updated_at"]:
                log(f"[SQL-CONN-SYNC] Change detected (new/update): {cid}")
                payload = {
                    "id": current["id"],
                    "scope": current["scope"],
                    "type": current["type"],
                    "params": json.loads(current["params"]),
                    "expires_at": current["expires_at"],
                }
                await callback(self._scope_to_topic(current["scope"]), payload)

        # 2. Find deleted constraints
        deleted_ids = self._last_known_constraints.keys() - current_constraints.keys()
        for cid in deleted_ids:
            log(f"[SQL-CONN-SYNC] Change detected (delete): {cid}")
            scope = self._last_known_constraints[cid]["scope"]
            await callback(self._scope_to_topic(scope), {})

        self._last_known_constraints = current_constraints
        log("[SQL-CONN-SYNC] Sync finished.")

    async def _poll_for_changes(self, callback: Callable):
        while self._is_connected:
            try:
                await asyncio.sleep(POLL_INTERVAL)
                log("[SQL-CONN-POLL] Polling for changes...")
                await self._sync_and_notify(callback)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"[SQL-CONN-POLL] Error: {e}")
                await asyncio.sleep(POLL_INTERVAL * 5)

    async def _uds_listener_loop(self, callback: Callable, ready_event: asyncio.Event):
        loop = asyncio.get_running_loop()
        transport = None
        try:
            Path(self.uds_path).unlink(missing_ok=True)
            log(f"[SQL-CONN-UDS] Creating datagram endpoint at {self.uds_path}")
            transport, _ = await loop.create_datagram_endpoint(
                lambda: UDSServerProtocol(self._uds_recv_event),
                local_addr=self.uds_path,
            )
            log("[SQL-CONN-UDS] Endpoint created. Signaling ready.")
            ready_event.set()
            while self._is_connected:
                await self._uds_recv_event.wait()
                self._uds_recv_event.clear()
                await self._sync_and_notify(callback)
        except asyncio.CancelledError:
            log("[SQL-CONN-UDS] Listener cancelled.")
        except Exception as e:
            log(f"[SQL-CONN-UDS] Listener error: {e}")
            ready_event.set()
        finally:
            if transport:
                transport.close()
            Path(self.uds_path).unlink(missing_ok=True)
            log("[SQL-CONN-UDS] Listener stopped and cleaned up.")
~~~~~

#### Acts 2: 更新测试装置以使用唯一的 UDS 路径

现在，我将修改 `test_e2e_sqlite_connector.py` 来利用这个新的 `uds_path` 参数，确保每个测试都在完全隔离的环境中运行。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~
~~~~~act
patch_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_polling_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
~~~~~

### 下一步建议
请重新运行测试。现在，终端应该会输出详细的日志流，精确地显示 `publish` 和 `subscribe` 路径中的每一步。这些信息将是定位问题的决定性证据。
