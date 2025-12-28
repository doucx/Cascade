import asyncio
import json
import sqlite3
import time
import sys
import socket
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle
from .uds_server import UdsTelemetryServer

POLL_INTERVAL = 0.2  # seconds
DEFAULT_UDS_PATH = "/tmp/cascade.sock"
DEFAULT_TELEMETRY_UDS_PATH = "/tmp/cascade-telemetry.sock"


class UDSServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, on_recv: asyncio.Event):
        self.on_recv = on_recv

    def datagram_received(self, data, addr):
        if not self.on_recv.is_set():
            self.on_recv.set()


class _LocalSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "LocalConnector", task: asyncio.Task):
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


class LocalConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
        uds_path: str = DEFAULT_UDS_PATH,
        telemetry_uds_path: str = DEFAULT_TELEMETRY_UDS_PATH,
    ):
        self.db_path = Path(db_path).expanduser()
        self.uds_path = uds_path
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._background_tasks: List[asyncio.Task] = []
        self._last_known_constraints: Dict[str, Dict[str, Any]] = {}
        self._use_polling = sys.platform == "win32"
        self._uds_recv_event = asyncio.Event()

        # UDS Telemetry Server (only for non-Windows platforms)
        self._telemetry_server: UdsTelemetryServer | None = None
        if not self._use_polling:
            self._telemetry_server = UdsTelemetryServer(telemetry_uds_path)

    async def connect(self) -> None:
        # Start telemetry server if it exists
        if self._telemetry_server:
            await self._telemetry_server.start()

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

        # Stop telemetry server
        if self._telemetry_server:
            await self._telemetry_server.stop()

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

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
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
        return _LocalSubscriptionHandle(self, task)

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
