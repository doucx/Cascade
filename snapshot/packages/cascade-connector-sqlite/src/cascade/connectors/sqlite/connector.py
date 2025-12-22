import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle

POLL_INTERVAL = 0.2  # seconds


class _SqliteSubscriptionHandle(SubscriptionHandle):
    """Implementation of the subscription handle for the SqliteConnector."""

    def __init__(
        self,
        parent: "SqliteConnector",
        polling_task: asyncio.Task,
    ):
        self._parent = parent
        self._polling_task = polling_task

    async def unsubscribe(self) -> None:
        self._polling_task.cancel()
        try:
            await self._polling_task
        except asyncio.CancelledError:
            pass
        self._parent._polling_tasks.remove(self._polling_task)


class SqliteConnector(Connector):
    """
    A Connector implementation using SQLite for persistence and polling for updates.
    This version is cross-platform compatible and has zero external dependencies.
    """

    def __init__(self, db_path: str = "~/.cascade/control.db"):
        self.db_path = Path(db_path).expanduser()
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._polling_tasks: List[asyncio.Task] = []
        self._last_check_ts = 0.0

    async def connect(self) -> None:
        def _connect_and_setup():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
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
            conn.commit()
            return conn

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
        self._is_connected = False
        
        # Cancel and await all polling tasks
        if self._polling_tasks:
            for task in self._polling_tasks:
                task.cancel()
            await asyncio.gather(*self._polling_tasks, return_exceptions=True)
            self._polling_tasks.clear()

        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    def _topic_to_scope(self, topic: str) -> str:
        # Converts "cascade/constraints/task/my_task" to "task:my_task"
        parts = topic.split("/")
        if len(parts) > 2 and parts[0:2] == ["cascade", "constraints"]:
            return ":".join(parts[2:])
        return topic # Fallback

    def _scope_to_topic(self, scope: str) -> str:
        # Converts "task:my_task" to "cascade/constraints/task/my_task"
        return f"cascade/constraints/{scope.replace(':', '/')}"

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        scope = self._topic_to_scope(topic)

        def _blocking_publish():
            cursor = self._conn.cursor()
            if not payload:  # Empty payload means resume/delete
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

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        # For simplicity, this connector broadcasts all changes to all subscribers.
        # Filtering based on the topic could be added if needed.
        task = asyncio.create_task(self._poll_for_changes(callback))
        self._polling_tasks.append(task)
        return _SqliteSubscriptionHandle(self, task)

    async def _poll_for_changes(
        self, callback: Callable[[str, Dict], Awaitable[None]]
    ):
        while self._is_connected:
            try:
                await asyncio.sleep(POLL_INTERVAL)

                def _blocking_fetch():
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "SELECT * FROM constraints WHERE updated_at > ?",
                        (self._last_check_ts,),
                    )
                    return cursor.fetchall()

                rows = await asyncio.to_thread(_blocking_fetch)

                if rows:
                    max_ts = self._last_check_ts
                    for row in rows:
                        payload = {
                            "id": row["id"],
                            "scope": row["scope"],
                            "type": row["type"],
                            "params": json.loads(row["params"]),
                            "expires_at": row["expires_at"],
                        }
                        topic = self._scope_to_topic(row["scope"])
                        await callback(topic, payload)
                        if row["updated_at"] > max_ts:
                            max_ts = row["updated_at"]
                    self._last_check_ts = max_ts
            except asyncio.CancelledError:
                break
            except Exception:
                # In a real implementation, add logging here
                await asyncio.sleep(POLL_INTERVAL * 5) # Backoff on error