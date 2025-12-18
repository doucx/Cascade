好的，测试已经稳定通过，现在我们将移除所有用于调试的临时代码，以保持测试套件的整洁。

## [WIP] refactor: 移除并发测试中的调试代码

### 用户需求
清理 `tests/py/runtime/test_engine_concurrency.py` 文件，移除所有临时添加的调试日志代码。

### 评论
调试代码对于诊断问题非常有用，但在问题解决后应立即移除，以避免污染代码库和测试输出。这是一个标准的开发卫生习惯。

### 目标
将 `test_engine_concurrency.py` 恢复到干净、无调试输出的最终状态。

### 基本原理
通过 `write_file` 操作，用一个完全清理过的文件版本覆盖现有文件，这是最直接和可靠的清理方式。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 清理测试文件

使用 `write_file` 完整覆盖测试文件，移除 `DEBUG_LOGS` 列表、`log()` 函数及其所有调用，并清理断言消息。

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
                # For testing purposes, we await the callback to ensure
                # the initial state is consistent before the engine starts scheduling.
                await callback(retained_topic, payload)

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

    # Pass dependencies as separate arguments so GraphBuilder detects them
    @cs.task
    def wrapper(res_a, res_b): return [res_a, res_b]
    
    workflow = wrapper(task_a(1), task_b(2))

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
我们已经完成了 Phase 3 中并发管理的核心实现和测试。现在是时候将这项工作作为一个逻辑单元提交了。我将为您准备一个 `[COMMIT]` 计划。
