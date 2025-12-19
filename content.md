简要回答
测试失败的根本原因是 **Retained Messages (保留消息)** 的分发逻辑发生了退化。在新的 `LocalBusConnector` 实现中，我们将保留消息放入了异步队列，由后台任务处理；而 Engine 在调用 `subscribe` 后会立即继续运行。由于后台任务的调度滞后，Engine 在还没感知到“暂停”或“速率限制”约束时就已经开始了任务执行，导致了竞态条件。

我将把保留消息的分发改回同步等待模式，确保 Engine 在 `subscribe` 返回时已经完整加载了所有现存约束。

## [WIP] fix(runtime): 恢复 LocalBusConnector 保留消息的确定性分发

### 错误分析
1.  **竞态条件 (Race Condition)**: `Engine.run()` 调用 `connector.subscribe("constraints/#", ...)`。
    - **当前逻辑**: `subscribe` 将现有的保留消息（如全局暂停）放入 `queue`，启动后台任务，然后立即返回。Engine 随即进入执行循环，认为当前没有约束。
    - **后果**: `test_startup_pause_is_respected` 中任务在暂停指令到达前就开始了；`test_e2e_ttl_expiration` 中 Engine 错过了初始约束，直接完成了任务。
2.  **解决方案**: 参照原 `InProcessConnector` 的可靠逻辑，在 `subscribe` 过程中**直接 `await` 回调函数**来处理保留消息。这确保了当 `subscribe` 函数返回给 Engine 时，`ConstraintManager` 已经同步更新了所有状态。

### 用户需求
确保工作流引擎在启动时能够 100% 确定地接收到环境中已存在的约束，消除 E2E 测试中的随机失败。

### 评论
在内存总线中，确定性高于并发性。通过同步分发初始状态，我们消除了对 `asyncio.sleep` 等模糊等待的依赖。

### 目标
1.  修改 `LocalBusConnector.subscribe`，在启动后台监听循环前，直接 `await` 处理所有匹配的保留消息。
2.  保持后续新消息依然通过异步队列处理。

### 基本原理
MQTT 的订阅机制要求在订阅成功时立即交付保留消息。在本地内存实现中，直接调用回调并 `await` 是实现这一契约最稳健的方式，它强制执行了“状态先于执行”的逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/telemetry #task/domain/telemetry #task/object/local-bus #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复订阅逻辑

我们将保留消息的分发改为直接 `await`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    # For immediate delivery, we can push to queue or call callback directly?
                    # Pushing to queue preserves order and simplifies locking.
                    await queue.put((retained_topic, payload))

        # Start a background listener for this specific subscription queue
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            # This ensures that when subscribe() returns, all existing 
            # state (constraints, etc.) has been processed by the engine.
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        print(f"[LocalBus] Retained Callback error on {retained_topic}: {e}")

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)
~~~~~

### 下一步建议
这是一个关键的逻辑修复。请再次运行 E2E 测试：
`pytest tests/py/e2e/`

如果通过，说明 `LocalBusConnector` 已经完全达到了“真空实验室”所需的确定性要求。我们可以继续 **里程碑 1.2**。
