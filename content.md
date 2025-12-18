# [WIP] fix: 修复并发测试中的 Mock 逻辑缺陷

### 错误分析
1.  **MockExecutor 参数处理错误**: `test_concurrency_constraint_on_map` 失败是因为 `MockExecutor` 忽略了 `kwargs`。在 `.map()` 生成的任务中，参数通常作为关键字参数传递。
2.  **MockConnector 时序竞争**: `test_global_concurrency_limit` 失败是因为测试试图在 `engine.run()` 启动后的短时间内注入约束，但这存在竞争条件。如果 `Engine` 在约束注入前就开始了任务调度，约束就会失效。

### 解决方案
1.  **增强 MockExecutor**: 更新其 `execute` 方法，使其能正确返回 `args[0]` 或 `kwargs` 中的第一个值。
2.  **增强 MockConnector**: 实现对**保留消息 (Retained Messages)** 的模拟。允许在测试开始前预置消息，并在 `subscribe` 被调用时立即触发回调。这准确模拟了 MQTT 的 Retained Message 行为，也是 Cascade 获取初始配置的标准方式。
3.  **重构测试**: 利用新的预置消息能力，消除 `asyncio.sleep` 带来的不确定性。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正测试文件

我们将重写 `tests/py/runtime/test_engine_concurrency.py`，更新 Mock 类并调整测试逻辑。

~~~~~act
write_file
tests/py/runtime/test_engine_concurrency.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node


# --- Mocks ---

class MockConnector(Connector):
    """
    A mock connector that simulates MQTT behavior, including Retained Messages.
    """

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        # Simulate broker storage for retained messages: topic -> payload
        self.retained_messages: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        pass

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to pre-seed a retained message on the broker."""
        self.retained_messages[topic] = payload

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback
        
        # Immediate delivery of matching retained messages upon subscription
        # This simulates MQTT behavior
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Dispatch in background to simulate async network I/O
                # ensuring subscribe returns quickly
                asyncio.create_task(callback(retained_topic, payload))

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a live message."""
        for sub_topic, callback in self.subscriptions.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                await callback(topic, payload)

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False


class MockExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Simulate work duration
        await asyncio.sleep(0.05)
        
        # Return the first available argument, or a default
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))
        return "result"


# --- Fixtures ---

@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=mock_connector,
        system_resources={}, 
    )


# --- Tests ---

@pytest.mark.asyncio
async def test_concurrency_constraint_on_map(engine, mock_connector):
    """
    Verify that a concurrency constraint limits the parallelism of a mapped task.
    """
    @cs.task
    def slow_task(x):
        return x

    inputs = [1, 2, 3, 4]
    workflow = slow_task.map(x=inputs)

    # 1. Pre-seed the constraint as a retained message.
    # This ensures it is applied immediately when the engine subscribes at startup.
    scope = "task:slow_task"
    payload = {
        "id": "limit-slow-task",
        "scope": scope,
        "type": "concurrency",
        "params": {"limit": 1}
    }
    mock_connector.seed_retained_message(
        f"cascade/constraints/{scope.replace(':', '/')}", payload
    )
    
    # 2. Run execution
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time
    
    assert sorted(results) == [1, 2, 3, 4]
    
    # With limit=1, 4 tasks of 0.05s should take >= 0.2s
    # (Allowing slight buffer for overhead, so maybe >= 0.18s)
    assert duration >= 0.18, f"Expected serial execution, got {duration}s"


@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    """
    Verify that a global concurrency constraint limits total tasks running.
    """
    @cs.task
    def task_a(x): return x
    
    @cs.task
    def task_b(x): return x

    # Two independent tasks, normally run in parallel
    wf = [task_a(1), task_b(2)]
    
    @cs.task
    def wrapper(results): return results
    workflow = wrapper(wf)

    # 1. Pre-seed Global Limit = 1
    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1}
    }
    mock_connector.seed_retained_message("cascade/constraints/global", payload)

    # 2. Run
    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time
    
    # 2 tasks of 0.05s in serial => >= 0.1s
    assert duration >= 0.09, f"Expected serial execution, got {duration}s"
~~~~~


### 下一步建议
我们已经完成了 Phase 3 中并发管理的核心逻辑。根据路线图，现在应该并行推进 Phase 4，实现 `cs-controller` 的对应命令 `set-limit`。这将为用户提供操作刚才实现的底层能力的界面。
