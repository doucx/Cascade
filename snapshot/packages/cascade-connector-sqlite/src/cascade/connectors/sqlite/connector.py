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