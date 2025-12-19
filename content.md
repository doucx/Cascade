好的，我们遇到了严重的 E2E 测试失败。这是重构过程中的关键时刻，失败的模式清晰地指向了一个根本性的问题。

## [WIP] fix(runtime): Make LocalBusConnector retained delivery synchronous

### 错误分析
E2E 测试套件的大规模失败，包括时序断言失败、死锁和约束未被遵守，都源于同一个根本原因：**我引入了一个微妙的启动竞态条件 (Startup Race Condition)**。

1.  **根本原因**: 新的 `LocalBusConnector` 将“保留消息 (Retained Messages)”的投递委托给了一个后台的异步监听任务。而旧的 (有缺陷的) `InProcessConnector` 是在 `subscribe` 方法内部**同步地**调用回调来投递这些消息的。
2.  **失败模式**: `Engine` 的启动逻辑依赖于一个隐式契约：当 `await connector.subscribe(...)` 调用返回时，所有相关的初始状态（如“全局暂停”约束）必须已经被处理。我的新实现破坏了这一契约。`subscribe` 方法会立即返回，而引擎则继续执行其调度逻辑。与此同时，后台任务才刚刚开始处理队列中的保留消息。在这个微小但致命的时间窗口内，引擎认为没有任何约束，并错误地开始执行任务，导致了所有后续的断言失败和死锁。
3.  **结论**: `test_harness_connector.py` 的失败也源于此。虽然它不使用保留消息，但它依赖于 `publish` 和 `subscribe` 之间的交互时序，而我引入的更复杂的队列和后台任务机制改变了这种时序，使得原有的 `asyncio.sleep(0.01)` 不再足以保证消息被处理。

**解决方案是恢复这种同步投递的确定性行为，这是引擎正确运行所必需的。**

### 用户需求
修复 `LocalBusConnector` 的实现，使其能够通过完整的 E2E 测试套件，确保系统的控制平面在各种时序条件下都能健壮、确定地工作。

### 评论
这是一个典型的、由看似微小的异步行为变化引发的连锁故障。它深刻地揭示了 `Engine` 与 `Connector` 之间隐藏的同步依赖关系。修复此问题将极大地增强我们测试套件和核心运行时的可靠性。

### 目标
修改 `LocalBusConnector.subscribe` 方法，使其在订阅时，同步地 `await` 匹配的保留消息的回调，然后再启动后台监听器处理新消息。

### 基本原理
通过在 `subscribe` 方法内部直接 `await` 回调，我们确保了在 `Engine` 继续执行之前，其状态（如 `ConstraintManager`）已经完全同步了来自“外部世界”的初始配置。这消除了竞态条件，使系统的启动行为变得完全确定。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/runtime #comp/tests #concept/telemetry #scope/core
#task/domain/telemetry #task/object/local-bus #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修复 `LocalBusConnector` 的 `subscribe` 逻辑

我们将修改 `subscribe` 方法，使其在返回前同步处理所有相关的保留消息。

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
        
        async with self._lock:
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

        # --- CRITICAL FIX START ---
        # Deliver retained messages SYNCHRONOUSLY before returning.
        # This closes the race condition window at engine startup.
        async with self._lock:
            retained_to_deliver = []
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    retained_to_deliver.append(
                        callback(retained_topic, payload)
                    )
            
            if retained_to_deliver:
                await asyncio.gather(*retained_to_deliver)
        # --- CRITICAL FIX END ---

        queue = asyncio.Queue()
        
        async with self._lock:
            self._subscriptions[topic].append(queue)

        # Start a background listener for NEW messages on this subscription.
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)
~~~~~

### 下一步建议
现在，根本问题已经修复。请再次运行完整的 E2E 测试套件：`pytest tests/py/e2e/`。

我预计所有之前失败的测试现在都将通过。一旦确认，我们就可以正式完成 **里程碑 1.1**，并开始进入激动人心的 **里程碑 1.2**：引擎的递归执行改造。
