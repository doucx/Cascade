import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle

POLL_INTERVAL = 0.2  # seconds


class _SqliteSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "SqliteConnector", polling_task: asyncio.Task):
        self._parent = parent
        self._polling_task = polling_task

    async def unsubscribe(self) -> None:
        self._polling_task.cancel()
        try:
            await self._polling_task
        except asyncio.CancelledError:
            pass
        if self._polling_task in self._parent._polling_tasks:
            self._parent._polling_tasks.remove(self._polling_task)


class SqliteConnector(Connector):
    def __init__(self, db_path: str = "~/.cascade/control.db"):
        self.db_path = Path(db_path).expanduser()
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._polling_tasks: List[asyncio.Task] = []
        self._last_known_constraints: Dict[str, Dict[str, Any]] = {}

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
            # Create an index for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS scope_idx ON constraints (scope)")
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
        if self._polling_tasks:
            for task in self._polling_tasks:
                task.cancel()
            await asyncio.gather(*self._polling_tasks, return_exceptions=True)
            self._polling_tasks.clear()
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
                        payload["id"], payload["scope"], payload["type"],
                        json.dumps(payload["params"]), payload.get("expires_at"),
                        time.time(),
                    ),
                )
            self._conn.commit()
        await asyncio.to_thread(_blocking_publish)

    async def subscribe(self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")
        
        # Initial Sync: Perform one poll immediately to catch pre-existing constraints
        await self._sync_and_notify(callback)

        task = asyncio.create_task(self._poll_for_changes(callback))
        self._polling_tasks.append(task)
        return _SqliteSubscriptionHandle(self, task)

    async def _sync_and_notify(self, callback: Callable):
        def _blocking_fetch_all():
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM constraints")
            return cursor.fetchall()

        rows = await asyncio.to_thread(_blocking_fetch_all)
        
        current_constraints: Dict[str, Dict] = {}
        for row in rows:
            constraint = dict(row)
            current_constraints[constraint["id"]] = constraint
        
        # --- Diff Logic ---
        # 1. Find new and updated constraints
        for cid, current in current_constraints.items():
            last = self._last_known_constraints.get(cid)
            if not last or last['updated_at'] < current['updated_at']:
                payload = {
                    "id": current["id"], "scope": current["scope"], "type": current["type"],
                    "params": json.loads(current["params"]), "expires_at": current["expires_at"]
                }
                await callback(self._scope_to_topic(current["scope"]), payload)

        # 2. Find deleted constraints
        deleted_ids = self._last_known_constraints.keys() - current_constraints.keys()
        for cid in deleted_ids:
            scope = self._last_known_constraints[cid]['scope']
            await callback(self._scope_to_topic(scope), {}) # Empty payload for resume

        self._last_known_constraints = current_constraints

    async def _poll_for_changes(self, callback: Callable):
        while self._is_connected:
            try:
                await asyncio.sleep(POLL_INTERVAL)
                await self._sync_and_notify(callback)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error in a real app
                await asyncio.sleep(POLL_INTERVAL * 5)