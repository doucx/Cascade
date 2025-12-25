Excellent. With the core `MockExecutor` and `MockConnector` now centralized, we can proceed to the next tier of test doubles.

Your analysis correctly identified `MockSolver` and `CaptureConnector` as the next targets. `MockSolver` is a classic "stub" that provides a canned response, perfect for isolating the `Engine` from the `Solver` logic.

Interestingly, the functionality of `CaptureConnector` (a "spy" for the `publish` method) is already provided by our new, robust `MockConnector` via its `publish_log` attribute. This is a great outcome, as we can replace a custom implementation with our new standard tool, further reducing code duplication.

Here is the plan to extract `MockSolver` and refactor the test that uses `CaptureConnector`.

## [WIP] refactor: Consolidate MockSolver and replace CaptureConnector

### 用户需求
1.  将 `test_engine_core.py`中的 `MockSolver` 提取到 `cascade.testing` 模块中。
2.  重构 `test_telemetry_contract.py`，用 `cascade.testing` 中通用的 `MockConnector` 替换其本地的 `CaptureConnector` 实现。

### 评论
这次重构有两个好处：一是将 `MockSolver` 这个重要的测试桩（stub）标准化，使其可被复用；二是通过移除 `CaptureConnector` 并改用 `MockConnector`，我们验证了通用测试工具的价值和设计，并进一步减少了项目中的冗余代码。

### 目标
1.  在 `packages/cascade-sdk/src/cascade/testing.py` 文件中添加 `MockSolver` 类。
2.  更新 `packages/cascade-engine/tests/runtime/test_engine_core.py`，移除本地的 `MockSolver` 定义，改为从 `cascade.testing` 导入。
3.  更新 `packages/cascade-cli-observer/tests/test_telemetry_contract.py`，移除 `CaptureConnector` 类，并修改测试逻辑以使用 `MockConnector` 的 `publish_log` 属性来捕获和断言 payload。

### 基本原理
我们将分三步完成此次重构。首先，通过 `write_file` 将 `MockSolver` 添加到 `cascade.testing` 中。接着，用 `write_file` 覆盖 `test_engine_core.py` 以使用新的导入。最后，用 `write_file` 覆盖 `test_telemetry_contract.py`，不仅移除旧的 `CaptureConnector`，还相应地调整了测试断言逻辑，以适配 `MockConnector` 记录发布历史的方式。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/cli #scope/dx #ai/instruct #task/domain/testing #task/object/test-doubles #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 将 MockSolver 添加到 `cascade.testing`

我们将 `MockSolver` 类添加到 `testing.py` 模块，使其成为一个可共享的测试工具。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Awaitable
from unittest.mock import MagicMock
import asyncio

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import Solver, Executor, ExecutionPlan, Connector
from cascade.graph.model import Node, Graph


@contextmanager
def override_resource(
    engine: "Engine", name: str, new_resource_func: Callable[[], Any]
):
    """
    A context manager to temporarily override a resource for testing purposes.

    Usage:
        engine = Engine()
        engine.register(production_db)

        with override_resource(engine, "production_db", mock_db):
            engine.run(my_task) # my_task will receive mock_db
    """
    if not hasattr(engine, "override_resource_provider"):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


class SpySolver(Solver):
    """
    A test double for the Solver protocol that spies on calls to `resolve`
    while delegating to a real underlying solver.
    """

    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol's type signature.
        # The actual call is handled by the `wraps` argument in __init__.
        pass


class MockSolver(Solver):
    """
    A test double for the Solver protocol that returns a pre-programmed plan,
    bypassing any real resolution logic.
    """

    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan regardless of the input graph
        return self._plan


class SpyExecutor(Executor):
    """A test double for the Executor protocol that logs all calls to `execute`."""

    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"


class MockExecutor(Executor):
    """
    A generic mock for the Executor protocol that can simulate various
    behaviors like delays or returning specific values.
    """



    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value


class MockConnector(Connector):
    """
    A mock connector for testing that simulates MQTT behavior,
    including retained messages and topic matching.
    """

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        # Simulate broker storage for retained messages: topic -> payload
        self.retained_messages: Dict[str, Dict[str, Any]] = {}
        self.connected: bool = False
        self.disconnected: bool = False
        self.publish_log: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True
        self.disconnected = False

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    async def publish(
        self, topic: str, payload: Dict[str, Any], retain: bool = False, qos: int = 0
    ) -> None:
        """Simulates publishing a message, triggering subscribers and handling retention."""
        self.publish_log.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

        if retain:
            if payload:
                self.retained_messages[topic] = payload
            elif topic in self.retained_messages:
                # An empty payload on a retained topic clears it
                del self.retained_messages[topic]

        await self._trigger_message(topic, payload)

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                asyncio.create_task(callback(retained_topic, payload))

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to pre-seed a retained message on the 'broker' for test setup."""
        self.retained_messages[topic] = payload

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message, used by tests and publish()."""
        for sub_topic, callback in self.subscriptions.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                await callback(topic, payload)

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        # Simple topic matching for direct match and wildcard at the end
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False
~~~~~

#### Acts 2: 重构 `test_engine_core.py`

现在，我们将更新 `test_engine_core.py` 以使用 `cascade.testing` 中的 `MockSolver`。

~~~~~act
write_file
packages/cascade-engine/tests/runtime/test_engine_core.py
~~~~~
~~~~~python
import pytest
from typing import List, Any, Dict

import cascade as cs
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.runtime import Engine, MessageBus, ExecutionPlan
from cascade.testing import SpyExecutor, MockSolver


# --- Test Case ---


@pytest.mark.asyncio
async def test_engine_follows_solver_plan():
    """
    Tests that Engine correctly iterates over the plan provided by a Solver
    and calls the Executor for each node in the correct order.
    """

    # 1. Define a simple workflow (the graph structure doesn't matter much
    # as the MockSolver will override the plan)
    @cs.task
    def task_a():
        pass

    @cs.task
    def task_b(x):
        pass

    workflow = task_b(task_a())
    graph, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")

    # 2. Define the execution plan that the MockSolver will return
    # A simple sequential plan: [A], then [B]
    mock_plan: ExecutionPlan = [[node_a], [node_b]]

    # 3. Setup test doubles and Engine
    solver = MockSolver(plan=mock_plan)
    executor = SpyExecutor()
    bus = MessageBus()

    engine = Engine(solver=solver, executor=executor, bus=bus)

    # 4. Run the engine
    await engine.run(workflow)

    # 5. Assert the executor was called in the correct order
    assert len(executor.call_log) == 2
    assert executor.call_log[0].name == "task_a"
    assert executor.call_log[1].name == "task_b"
~~~~~

#### Acts 3: 重构 `test_telemetry_contract.py`

最后，我们将用 `MockConnector` 替换 `CaptureConnector`，并相应地调整测试代码。

~~~~~act
write_file
packages/cascade-cli-observer/tests/test_telemetry_contract.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock

from cascade.runtime.events import TaskExecutionFinished
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.cli.observer.app import on_message
from cascade.testing import MockConnector


@pytest.mark.asyncio
async def test_telemetry_subscriber_to_observer_contract():
    """
    Verifies that the JSON produced by TelemetrySubscriber is correctly
    consumed by the cs-observer's on_message handler.
    """
    # 1. ARRANGE: Producer side
    connector = MockConnector()
    subscriber = TelemetrySubscriber(MagicMock(), connector)

    # 2. PRODUCE: Create a runtime event and have the subscriber process it
    event = TaskExecutionFinished(
        run_id="run-contract-test",
        task_id="task-abc",
        task_name="contract_task",
        status="Succeeded",
        duration=0.123,
    )
    subscriber.on_event(event)

    # Let the asyncio.create_task in on_event run
    await asyncio.sleep(0.01)

    # 3. ASSERT: The payload was captured in the publish log
    assert len(connector.publish_log) == 1
    produced_payload = connector.publish_log[0]["payload"]

    assert produced_payload is not None
    assert produced_payload["run_id"] == "run-contract-test"
    assert produced_payload["body"]["task_name"] == "contract_task"

    # 4. ARRANGE: Consumer side
    mock_bus = MagicMock()

    # 5. CONSUME: Feed the produced JSON directly to the observer's handler
    # We patch the bus used by the observer to intercept the result
    observer_app_bus_path = "cascade.cli.observer.app.bus"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(observer_app_bus_path, mock_bus)
        await on_message("a/topic", produced_payload)

    # 6. ASSERT: The observer called the bus with the correct, parsed information
    mock_bus.info.assert_any_call(
        "observer.telemetry.task_state.COMPLETED",
        task_name="contract_task",
        duration_ms=123.0,
        error="",
    )
~~~~~
