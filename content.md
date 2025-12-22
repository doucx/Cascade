好的，我收到了测试结果。您是正确的，指出“流程正常”意味着我们遵循了“开发->测试->发现问题->修复”的健康循环。测试发现了两个明确的失败场景，现在我的任务是分析并修复它们。

这是一个旨在修复这两个已识别错误的计划。

## [WIP] fix(connector-sqlite): 修复轮询逻辑以处理删除并消除启动竞争

### 错误分析
测试套件暴露了两个独立的、严重的问题，导致了测试失败：

1.  **`test_polling_pause_and_resume_e2e` 失败**:
    *   **症状**: `task_b` 在被命令暂停后依然执行了。仔细分析后发现，暂停命令生效了，但后续的**恢复命令（resume）被忽略了**。
    *   **根本原因**: 当前的轮询逻辑 `SELECT ... WHERE updated_at > ?` 只能检测到行的**插入（insert）和更新（update）**。恢复命令是通过**删除（delete）**行来实现的。被删除的行自然不会出现在查询结果中，因此轮询机制完全“看不见”恢复操作，导致 `Engine` 永远不会收到恢复通知，任务保持暂停状态直到测试超时失败。

2.  **`test_constraint_ttl_expiration_e2e` 失败**:
    *   **症状**: `Engine` 任务立即完成了（`engine_run_task.done()` 为 `True`），而不是像预期的那样被带有 TTL 的 `pause` 约束所阻塞。
    *   **根本原因**: 这是一个典型的**启动竞争条件（startup race condition）**。测试用例在 `Engine` 启动**之前**就发布了约束。然而，`SqliteConnector` 的 `subscribe` 方法立即返回并启动了一个在后台轮询的异步任务。`Engine` 没有等待第一次轮询完成，而是立即开始执行工作流。工作流非常快，在后台的轮询任务第一次唤醒并从数据库读到约束之前，它就已经执行完毕了。

### 用户需求
修复 `SqliteConnector` 的实现，以解决删除操作无法被检测和启动时竞争条件的问题，从而使所有 E2E 测试都能通过。

### 评论
这两个都是非常关键的逻辑缺陷。修复它们将使 `SqliteConnector` 的行为与 `MqttConnector`（支持保留消息和明确的删除/空消息）更加一致，从而变得更加健壮和可预测。

-   对于**恢复/删除问题**，我们将把轮询机制从“基于时间戳的增量更新”模型升级为“**基于全量快照的差异（diff）对比**”模型。连接器将在内存中维护一份上次看到的所有约束的快照。每次轮询时，它会获取数据库中的**所有**当前约束，并与内存快照进行对比，从而精确地计算出哪些约束被添加/更新，哪些被删除。

-   对于**启动竞争问题**，我们将在 `subscribe` 方法中引入一个**初始同步（initial sync）**步骤。在启动后台轮询循环之前，它将立即、阻塞地（通过 `to_thread`）执行一次全量数据获取和回调。这确保了 `Engine` 在开始执行任何任务之前，其状态就与数据库的当前状态完全同步，完美地模拟了 MQTT 的保留消息（retained message）行为。

### 目标
1.  修改 `SqliteConnector` 的 `subscribe` 方法，在启动后台轮询任务之前，执行一次性的、同步的初始数据拉取，并将任何已存在的约束立即通知给 `Engine`。
2.  重构 `_poll_for_changes` 方法和 `SqliteConnector` 的内部状态，使其维护一个 `_last_known_constraints` 字典作为内存快照。
3.  修改轮询逻辑，使其每次都查询所有约束，然后与内存快照进行对比，以识别新增、变更和被删除的约束。
4.  确保在检测到约束被删除时，向 `Engine` 回调一个带有空 payload 的消息，以触发恢复逻辑。

### 基本原理
此计划将使用一个 `write_file` 操作来完全替换 `packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py` 的内容。鉴于逻辑变更的范围较大（引入了状态快照、差异对比和初始同步），一次性重写比多个零碎的 `patch` 操作更清晰、更不容易出错。

新的实现将包含一个 `_sync_and_notify` 的辅助方法，它封装了“查询所有约束、与快照对比、发送通知、更新快照”的核心逻辑。`subscribe` 方法将首先调用这个辅助方法以完成初始同步，然后后台的 `_poll_for_changes` 任务将在循环中反复调用它。

### 标签
#intent/fix #flow/ready #priority/critical #comp/connector-sqlite #concept/state #concept/sync #ai/refine #task/domain/connectors #task/object/sqlite-connector #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 应用修复后的 `SqliteConnector` 实现

我们将用一个实现了“初始同步”和“差异化轮询”的、更健壮的版本来替换现有的 `connector.py`。

~~~~~act
write_file
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
我们已经对 `SqliteConnector` 的核心逻辑进行了重大重构，以解决之前测试中发现的两个关键问题。现在，新的实现应该能够正确处理约束的删除（恢复）操作，并且不会再有启动时的竞争条件。

请再次运行测试套件。如果所有测试都通过，我们就可以确认第一步（奠定基石）已圆满完成，并可以自信地进入**步骤 2：[性能优化] 增强 Unix Domain Socket (UDS) 信号机制**。
