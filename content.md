是的，这确实是同样的问题：**时序竞争**。

在当前的测试代码中，Engine 启动得太快了，在 Controller 发布约束之前，Engine 就已经完成了任务调度。而且，我们的 `InProcessConnector` 实现过于简单，没有真正实现 **MQTT Retained Messages（保留消息）** 的逻辑——即“后来的订阅者也能收到之前发布的消息”。

要修复这个问题并建立一个坚如磐石的 E2E 测试，我们需要：
1.  **升级 `InProcessConnector`**：使其真正支持 `retain=True`，即把消息存下来，并在新订阅发生时立即重放。
2.  **调整测试顺序**：先由 Controller 发布约束（模拟预设环境配置），然后再启动 Engine。这样 Engine 一启动并订阅，就会立即收到约束，从而在执行任何任务前应用限制。

这是修复方案：

## [WIP] fix: 升级 InProcessConnector 以支持保留消息

### 用户需求
修复 E2E 测试中的时序竞争问题。

### 评论
当前的 `InProcessConnector` 只是一个简单的广播器。为了模拟真实世界的 MQTT 行为（特别是配置下发场景），它必须具备“记忆”能力。通过实现保留消息机制，我们可以让 Controller 先发布配置，Engine 后启动并自动获取配置，从而消除对 `sleep` 的依赖和竞争条件。

### 目标
1.  修改 `tests/py/e2e/test_e2e_concurrency_control.py`。
2.  在 `InProcessConnector` 中添加 `_retained_messages` 存储。
3.  更新 `publish` 方法以存储保留消息。
4.  更新 `subscribe` 方法以在订阅时立即重放保留消息。
5.  调整测试逻辑：先发布约束，后运行 Engine。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/e2e-test #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 E2E 测试文件

我们将重写整个文件，因为 `InProcessConnector` 的逻辑变更涉及类的多个方法，且测试流程也需要调整。

~~~~~act
write_file
tests/py/e2e/test_e2e_concurrency_control.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


# --- Test Infrastructure: In-Process Communication ---

class InProcessConnector(Connector):
    """
    A Connector that uses asyncio Queues for in-process, in-memory message passing.
    Now supports MQTT-style Retained Messages for robust config delivery.
    """
    _instance = None
    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        # Reset state for each test instantiation if needed, 
        # but here we rely on new instances per test via fixtures usually.
        # Since we use class-level dicts for sharing, we should clear them if reusing classes.
        # For this file, let's clear them in __init__ to be safe given the test runner.
        self._shared_topics.clear()
        self._retained_messages.clear()

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        # 1. Handle Retention
        if retain:
            self._retained_messages[topic] = payload

        # 2. Live Dispatch
        # Find all queues subscribed to this topic and put the message
        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)
        
        # 1. Replay Retained Messages immediately (Async task to simulate network)
        # We find all retained messages that match this new subscription
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await queue.put((retained_topic, payload))

        # 2. Start listener
        asyncio.create_task(self._listen_on_queue(queue, callback))

    async def _listen_on_queue(self, queue: asyncio.Queue, callback):
        while True:
            try:
                topic, payload = await queue.get()
                await callback(topic, payload)
                queue.task_done()
            except asyncio.CancelledError:
                break

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False


class ControllerTestApp:
    """A lightweight simulator for the cs-controller CLI tool."""
    def __init__(self, connector: Connector):
        self.connector = connector

    async def set_concurrency_limit(self, scope: str, limit: int):
        constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="concurrency",
            params={"limit": limit},
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


class MockWorkExecutor(Executor):
    """Executor that simulates time-consuming work."""
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        await asyncio.sleep(0.05)
        if kwargs:
            return next(iter(kwargs.values()))
        return "result"


# --- The E2E Test ---

@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller publishes constraint (Retained).
    2. Engine starts, connects, receives config, AND THEN executes.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()

    # 2. Setup the Controller
    controller = ControllerTestApp(connector)

    # 3. Publish the constraint FIRST (Simulating existing environment config)
    # Limit task concurrency to 1
    await controller.set_concurrency_limit(scope="task:slow_task", limit=1)

    # 4. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    # 6. Run the engine (Blocking call, simpler than background task for this flow)
    # The Engine will:
    #   a. Connect
    #   b. Subscribe to constraints/#
    #   c. Receive the retained 'limit=1' message -> Update ConstraintManager
    #   d. Build graph and start scheduling
    #   e. See constraint and throttle execution
    
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s.
    assert duration >= 0.18, f"Expected serial execution (~0.2s), but took {duration:.4f}s"
~~~~~

### 下一步建议
现在 E2E 测试遵循了正确的“先配置，后运行”模式，并且 `InProcessConnector` 正确实现了保留消息机制，测试应该能够稳定通过。

通过后，我们将提交这个测试文件，然后我可以为您生成最终的 `[COMMIT]` 计划。
