非常好！这些日志给了我们决定性的线索。问题已经定位了。

## [WIP] fix(connector): Specify AF_UNIX family for UDS endpoint

### 错误分析
日志中的关键一行是：

`[SQL-CONN-UDS] Listener error: 2-tuple is expected`

这个错误来自于 `asyncio` 的底层 `create_datagram_endpoint` 方法。这是问题的根本原因，它揭示了一个低级的 API 误用：

1.  **错误的 Socket Family**: 当我们调用 `create_datagram_endpoint` 时，我没有指定 `family` 参数。它很可能默认使用了 `socket.AF_INET`（用于 TCP/IP 网络通信），这个 family 的 `local_addr` 参数需要一个 `(host, port)` 的二元元组。
2.  **API 不匹配**: 然而，我们为 Unix Domain Sockets 提供的是一个字符串路径（例如 `/tmp/.../cascade_test.sock`），而不是一个元组。这就导致了 `TypeError: 2-tuple is expected`。
3.  **正确的用法**: 为了让 `asyncio` 正确处理文件系统路径，我们**必须**明确地指定 `family=socket.AF_UNIX`。

这个初始化错误导致了连锁反应：
1.  UDS 监听任务在尝试绑定 socket 时立即崩溃。
2.  我的 `try...except` 块捕获了异常，但错误地设置了 `ready_event`，这向 `subscribe` 方法谎报“监听器已就绪”。
3.  `subscribe` 方法继续执行初始同步，正确地加载了第一个（慢速）约束。
4.  当测试发布第二个（快速）约束时，`publish` 方法尝试发送 UDS 信号。但由于监听器从未成功启动，所以日志显示 `UDS signal failed: No listener.`
5.  `Engine` 从未被唤醒以处理数据库中的更新，因此它继续受制于旧的、慢速的约束，最终导致测试超时。

### 用户需求
修复由错误的 socket family 导致的 UDS 监听器启动失败问题，使 `e2e` 测试能够通过。

### 评论
这是一个典型的、因依赖默认参数而非显式声明意图而导致的底层错误。日志在这里起到了决定性作用，它将问题从复杂的“状态同步逻辑”缩小到了一个简单的“API 调用参数”问题。

### 目标
1.  定位到 `SqliteConnector._uds_listener_loop` 方法中的 `create_datagram_endpoint` 调用。
2.  为其添加 `family=socket.AF_UNIX` 参数。
3.  移除之前添加的诊断性日志，因为问题已经明确。

### 基本原理
通过显式声明 `family=socket.AF_UNIX`，我们告诉 `asyncio` 的事件循环，我们提供的 `local_addr` 是一个文件系统路径，而不是网络地址。这将使其能够正确创建和绑定 Unix Domain Socket，从而修复监听器，让整个信号机制正常工作。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/sqlite-connector #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 UDS 端点创建并移除日志

我将一次性重写整个文件，应用 `family=socket.AF_UNIX` 的修复，并移除所有为了调试而添加的 `log()` 调用和函数，使代码恢复整洁。

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


class UDSServerProtocol(asyncio.DatagramProtocol):
    """Protocol that sets an event when a datagram is received."""

    def __init__(self, on_recv: asyncio.Event):
        self.on_recv = on_recv

    def datagram_received(self, data, addr):
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

        if not self._use_polling:
            await self._send_uds_signal()

    async def _send_uds_signal(self):
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.sendto(b"\x01", self.uds_path)
        except (ConnectionRefusedError, FileNotFoundError, BlockingIOError):
            pass
        except Exception:
            pass
        finally:
            if sock:
                sock.close()

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")
        ready_event = asyncio.Event()

        if self._use_polling:
            task = asyncio.create_task(self._poll_for_changes(callback))
            ready_event.set()
        else:
            task = asyncio.create_task(self._uds_listener_loop(callback, ready_event))
        self._background_tasks.append(task)
        await ready_event.wait()
        await self._sync_and_notify(callback)
        return _SqliteSubscriptionHandle(self, task)

    async def _sync_and_notify(self, callback: Callable):
        def _blocking_fetch_all():
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM constraints")
            return cursor.fetchall()

        rows = await asyncio.to_thread(_blocking_fetch_all)
        current_constraints: Dict[str, Dict] = {dict(r)["id"]: dict(r) for r in rows}

        for cid, current in current_constraints.items():
            last = self._last_known_constraints.get(cid)
            if not last or last["updated_at"] < current["updated_at"]:
                payload = {
                    "id": current["id"],
                    "scope": current["scope"],
                    "type": current["type"],
                    "params": json.loads(current["params"]),
                    "expires_at": current["expires_at"],
                }
                await callback(self._scope_to_topic(current["scope"]), payload)

        deleted_ids = self._last_known_constraints.keys() - current_constraints.keys()
        for cid in deleted_ids:
            scope = self._last_known_constraints[cid]["scope"]
            await callback(self._scope_to_topic(scope), {})

        self._last_known_constraints = current_constraints

    async def _poll_for_changes(self, callback: Callable):
        while self._is_connected:
            try:
                await asyncio.sleep(POLL_INTERVAL)
                await self._sync_and_notify(callback)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(POLL_INTERVAL * 5)

    async def _uds_listener_loop(self, callback: Callable, ready_event: asyncio.Event):
        loop = asyncio.get_running_loop()
        transport = None
        try:
            Path(self.uds_path).unlink(missing_ok=True)
            transport, _ = await loop.create_datagram_endpoint(
                lambda: UDSServerProtocol(self._uds_recv_event),
                local_addr=self.uds_path,
                family=socket.AF_UNIX,
            )
            ready_event.set()
            while self._is_connected:
                await self._uds_recv_event.wait()
                self._uds_recv_event.clear()
                await self._sync_and_notify(callback)
        except asyncio.CancelledError:
            pass
        except Exception:
            ready_event.set()
        finally:
            if transport:
                transport.close()
            Path(self.uds_path).unlink(missing_ok=True)
~~~~~

### 下一步建议
请再次运行测试。这次修复是针对日志中发现的根本原因，我非常有信心它能解决问题。如果测试通过，我们就可以继续路线图的步骤 4，编写新的测试用例来专门验证 UDS 的快速唤醒行为。
