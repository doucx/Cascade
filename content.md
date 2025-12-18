为了深入诊断问题，我将在 `MockConnector` 和 `ConcurrencyConstraintHandler` 中注入调试信息。由于无法直接查看 stdout，我将通过收集日志并在测试失败时抛出包含日志的异常来暴露内部状态。

### Script

#### Acts 1: 注入调试代码到测试文件

我将修改 `tests/py/runtime/test_engine_concurrency.py`，增加一个全局日志列表，并在关键位置记录执行路径。最后在 `test_global_concurrency_limit` 中，如果断言失败，将打印这些日志。

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

# --- DEBUGGING ---
DEBUG_LOGS = []
def log(msg):
    DEBUG_LOGS.append(msg)

# --- Mocks ---

class MockConnector(Connector):
    """
    A mock connector that simulates MQTT behavior, including Retained Messages.
    """

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self.retained_messages: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        log("MockConnector: connected")

    async def disconnect(self) -> None:
        pass

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        pass

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
        log(f"MockConnector: seeding retained message for {topic}")
        self.retained_messages[topic] = payload

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        log(f"MockConnector: subscribing to {topic}")
        self.subscriptions[topic] = callback
        
        count = 0
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                log(f"MockConnector: delivering retained message for {retained_topic}")
                await callback(retained_topic, payload)
                count += 1
        log(f"MockConnector: delivered {count} retained messages")

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
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
        log(f"MockExecutor: executing {node.name}")
        await asyncio.sleep(0.05)
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))
        return "result"


# --- Fixtures ---

@pytest.fixture
def mock_connector():
    # Clear logs for each test
    DEBUG_LOGS.clear()
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
    @cs.task
    def slow_task(x):
        return x

    inputs = [1, 2, 3, 4]
    workflow = slow_task.map(x=inputs)

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
    
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time
    
    assert sorted(results) == [1, 2, 3, 4]
    assert duration >= 0.18, f"Expected serial execution, got {duration}s. Logs: {DEBUG_LOGS}"


@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    @cs.task
    def task_a(x): return x
    
    @cs.task
    def task_b(x): return x

    wf = [task_a(1), task_b(2)]
    
    @cs.task
    def wrapper(results): return results
    workflow = wrapper(wf)

    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1}
    }
    mock_connector.seed_retained_message("cascade/constraints/global", payload)

    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time
    
    assert duration >= 0.09, f"Expected serial execution, got {duration}s. Logs: {DEBUG_LOGS}"
~~~~~

我将运行此测试，如果它再次失败，错误信息中包含的 `Logs` 将揭示是回调没有被触发，还是 Executor 没有被阻塞。
