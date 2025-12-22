分析完毕。你发现了一个非常关键的竞争条件 (Race Condition)，这也是导致两个测试都失败的根本原因。我的 UDS 实现中存在一个逻辑缺陷。

## [WIP] fix(connector): Correct race condition in SqliteConnector subscribe logic

### 错误分析
两个测试失败的根本原因相同：在 `SqliteConnector` 的 `subscribe` 方法中存在一个微妙的竞争条件。

**问题根源**:
我当前实现的 `subscribe` 逻辑是：
1.  首先，执行一次 `_sync_and_notify` 来获取数据库中的所有**现有**约束。
2.  然后，创建并启动后台任务（`_uds_listener_loop` 或 `_poll_for_changes`）来监听**未来**的变更。

**竞争窗口**:
在步骤 1 和步骤 2 之间存在一个极小但致命的时间窗口。如果一个 `controller.publish()` 操作恰好在这个窗口期发生，会发生以下情况：
1.  它的变更**不会**被初始的 `_sync_and_notify` 捕获，因为它发生在同步之后。
2.  它发出的 UDS 信号会丢失，因为它发生在 `_uds_listener_loop` 开始真正在 UDS 套接字上监听之前。

**对测试的影响**:
1.  `test_polling_pause_and_resume_e2e`: 测试在 `slow_task_a` 运行时发布 `pause` 约束。这个发布操作有很大概率落入上述竞争窗口。因此，`Engine` 从未收到 `pause` 约束，导致 `task_b` 在 `task_a` 完成后立即执行，引发断言失败。
2.  `test_constraint_update_idempotency_e2e`: 测试发布了一个慢速的速率限制，然后发布一个快速的。第二个（快速的）发布操作同样可能落入竞争窗口，其 UDS 信号丢失。`Engine` 从未收到更新，继续在慢速限制下运行，最终导致等待 `engine_run_task` 时超时。

**解决方案**:
必须颠倒 `subscribe` 方法中的操作顺序。正确的、无竞争的逻辑是：
1.  **首先**，创建并启动后台监听任务。这样可以确保我们已经准备好接收任何新的信号。
2.  **然后**，执行初始的 `_sync_and_notify`。

通过这种方式，如果在初始同步期间有新的发布操作发生，它的 UDS 信号会被已经激活的监听器捕获，从而保证状态的最终一致性。

### 用户需求
修复 `test_e2e_sqlite_connector.py` 中由于 `SqliteConnector` 的竞争条件而失败的两个测试。

### 评论
这是一个典型的异步编程中的微妙错误，它暴露了在处理状态同步和事件通知时原子性操作的重要性。这个修复对于确保 `SqliteConnector` 在高并发或快速连续操作下的可靠性至关重要。

### 目标
1.  修改 `SqliteConnector.subscribe` 方法的内部逻辑顺序。
2.  确保后台监听任务在初始状态同步之前被创建和启动。
3.  使所有现存的 `e2e` 测试通过。

### 基本原理
修复的基本原理是消除`subscribe`方法中的竞争窗口。通过确保监听机制（无论是轮询还是 UDS）在执行初始状态同步（从数据库拉取数据）之前就已完全激活，我们可以保证任何在同步过程中或之后发生的更新都会被正确捕获，从而防止状态更新的丢失。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/sqlite-connector #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `subscribe` 方法中的逻辑顺序

我将使用 `patch_file` 来精确地重构 `subscribe` 方法，消除竞争条件。

~~~~~act
patch_file
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        await self._sync_and_notify(callback)

        if self._use_polling:
            task = asyncio.create_task(self._poll_for_changes(callback))
        else:
            task = asyncio.create_task(self._uds_listener_loop(callback))

        self._background_tasks.append(task)
        return _SqliteSubscriptionHandle(self, task)
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        # Start the listener task FIRST to prevent a race condition where a publish
        # could happen after the initial sync but before the listener is active.
        if self._use_polling:
            task = asyncio.create_task(self._poll_for_changes(callback))
        else:
            task = asyncio.create_task(self._uds_listener_loop(callback))

        self._background_tasks.append(task)

        # Now, perform the initial sync. Any changes that occurred during listener
        # setup will either be caught here or their UDS signal will have been
        # queued for the now-active listener.
        await self._sync_and_notify(callback)

        return _SqliteSubscriptionHandle(self, task)
~~~~~

### 下一步建议
在应用这个修复之后，我们应该重新运行完整的测试套件。如果所有测试都通过了，我们就可以自信地继续执行原计划的下一步：为 UDS 的特定行为编写新的、专门的测试用例，以完成路线图的步骤 4。
