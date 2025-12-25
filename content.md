当然，我们继续推进测试工具的重构。将 `MockConnector` 提取并通用化是继 `MockExecutor` 之后最合理的步骤，这将进一步减少测试代码的重复，并提供一个更强大、行为更一致的测试替身。

我将生成一个计划，首先在 `cascade.testing` 模块中创建一个统一的、功能完备的 `MockConnector`，然后重构 `test_engine_concurrency.py` 和 `test_engine_constraints.py` 以使用这个新的通用组件。

## [WIP] refactor: 将 MockConnector 整合到 cascade.testing

### 用户需求
将 `test_engine_concurrency.py` 和 `test_engine_constraints.py` 中各自的 `MockConnector` 实现合并为一个功能更全面的版本，并将其迁移到 `cascade.testing` 模块中，供所有测试共享使用。

### 评论
这是一个优秀的重构任务。它遵循了 Don't Repeat Yourself (DRY) 原则，将测试基础设施集中化。一个强大且统一的 `MockConnector` 不仅能简化现有测试，还能使未来编写依赖 `Connector` 协议的测试变得更加容易和可靠。

### 目标
1.  在 `packages/cascade-sdk/src/cascade/testing.py` 中创建一个新的 `MockConnector` 类。这个类将整合现有两个版本的功能，特别是对 retained messages 的支持。
2.  同时，基于你之前的说明，在 `cascade.testing` 中添加一个通用的 `MockExecutor`，它能够模拟执行延迟。
3.  重构 `packages/cascade-engine/tests/runtime/test_engine_concurrency.py`，移除其本地的 `MockConnector` 和 `MockExecutor` 定义，转而从 `cascade.testing` 导入并使用它们。
4.  同样地，重构 `packages/cascade-engine/tests/runtime/test_engine_constraints.py`，使其也依赖于 `cascade.testing` 中新的测试辅助类。

### 基本原理
我们采取与 `MockExecutor` 相同的整合策略。通过分析 `test_engine_concurrency.py` 中的实现（它包含了对 retained acks 的关键模拟，这是 MQTT 的一个核心特性），我们将其作为新 `MockConnector` 的蓝本。然后，我们确保新版本也涵盖了 `test_engine_constraints.py` 中的用例。最终，我们用一个 `write_file` 操作更新 `cascade.testing` 模块，并用另外两个 `write_file` 操作以原子方式替换掉旧的测试文件内容，确保它们能无缝地切换到新的通用测试工具上。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/test-doubles #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 创建通用的 MockExecutor 和 MockConnector

首先，我们将更新 `cascade.testing` 模块，加入一个全新的、功能更全面的 `MockConnector`，以及一个可配置延迟的 `MockExecutor`。

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

#### Acts 2: 重构并发测试

现在，我们将重构 `test_engine_concurrency.py`，移除本地的辅助类，并切换到 `cascade.testing` 中的新实现。

~~~~~act
write_file
packages/cascade-engine/tests/runtime/test_engine_concurrency.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List

import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.testing import MockConnector, MockExecutor


# --- Fixtures ---


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
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
        "params": {"limit": 1},
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
    def task_a(x):
        return x

    @cs.task
    def task_b(x):
        return x

    # Pass dependencies as separate arguments so GraphBuilder detects them
    @cs.task
    def wrapper(res_a, res_b):
        return [res_a, res_b]

    workflow = wrapper(task_a(1), task_b(2))

    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1},
    }
    mock_connector.seed_retained_message("cascade/constraints/global", payload)

    # 2. Run
    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time

    # 2 tasks of 0.05s in serial => >= 0.1s
    assert duration >= 0.09, f"Expected serial execution, got {duration}s"
~~~~~

#### Acts 3: 重构约束测试

最后，我们对 `test_engine_constraints.py` 执行同样的操作，完成整个重构。

~~~~~act
write_file
packages/cascade-engine/tests/runtime/test_engine_constraints.py
~~~~~
~~~~~python
import asyncio
from typing import Callable, Awaitable, Dict, Any

import pytest

from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.spec.constraint import GlobalConstraint
from cascade.testing import MockConnector, MockExecutor


# --- Test Fixtures and Mocks ---


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
    )


async def wait_for_task_finish(spy, task_name: str, timeout: float = 2.0):
    """Helper coroutine to wait for a specific task to finish."""
    from cascade.runtime.events import TaskExecutionFinished

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        finished_events = spy.events_of_type(TaskExecutionFinished)
        if any(e.task_name == task_name for e in finished_events):
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Timeout waiting for task '{task_name}' to finish.")


async def wait_for_task_start(spy, task_name: str, timeout: float = 2.0):
    """Helper coroutine to wait for a specific task to start."""
    from cascade.runtime.events import TaskExecutionStarted

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        started_events = spy.events_of_type(TaskExecutionStarted)
        if any(e.task_name == task_name for e in started_events):
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"Timeout waiting for task '{task_name}' to start.")


# --- Test Cases ---


@pytest.mark.asyncio
async def test_engine_subscribes_to_constraints(engine_with_connector, mock_connector):
    """
    Verify that the Engine subscribes to the correct topic upon starting a run.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    await engine_with_connector.run(dummy_task())

    # Assert that subscribe was called with the correct topic
    # The actual topic is cascade/constraints/#, our mock logic handles the match
    assert "cascade/constraints/#" in mock_connector.subscriptions
    assert callable(mock_connector.subscriptions["cascade/constraints/#"])


@pytest.mark.asyncio
async def test_engine_updates_constraints_on_message(
    engine_with_connector, mock_connector
):
    """
    Verify that the Engine's ConstraintManager is updated when a valid message is received.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Simulate receiving a constraint message
    constraint_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        "cascade/constraints/control", constraint_payload
    )

    # Check the internal state of the ConstraintManager
    constraint_manager = engine_with_connector.constraint_manager
    stored_constraint = constraint_manager._constraints.get("global-pause")

    assert stored_constraint is not None
    assert isinstance(stored_constraint, GlobalConstraint)
    assert stored_constraint.id == "global-pause"
    assert stored_constraint.scope == "global"
    assert stored_constraint.type == "pause"

    # Allow the run to complete
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_engine_handles_malformed_constraint_payload(
    engine_with_connector, mock_connector, capsys
):
    """
    Verify that the Engine logs an error but does not crash on a malformed payload.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Wait until subscription is established
    for _ in range(50):
        if "cascade/constraints/#" in mock_connector.subscriptions:
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timeout waiting for engine to subscribe to constraints")

    # Payload missing the required 'id' key
    malformed_payload = {
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        "cascade/constraints/control", malformed_payload
    )

    # The engine should not have crashed.
    # We can check stderr for the error message.
    captured = capsys.readouterr()
    assert "[Engine] Error processing constraint" in captured.err
    assert "'id'" in captured.err  # Specifically mentions the missing key

    # Assert that no constraint was added
    assert not engine_with_connector.constraint_manager._constraints

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_engine_pauses_on_global_pause_constraint(mock_connector, bus_and_spy):
    """
    End-to-end test verifying the global pause functionality.
    It checks that after a pause command is received, no new tasks are started.
    """
    from cascade.spec.task import task
    from cascade.runtime.events import TaskExecutionStarted

    bus, spy = bus_and_spy
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Define a declarative workflow
    @task
    def task_a():
        return "A"

    @task
    def task_b(a):
        return f"B after {a}"

    @task
    def task_c(b):
        return f"C after {b}"

    workflow = task_c(b=task_b(a=task_a()))

    # 2. Start the engine in a concurrent task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for the first task to START.
    # We want to inject the pause while A is running (or at least before B starts).
    # Since Engine awaits tasks in a stage, injecting here ensures the constraint
    # is ready when Engine wakes up for Stage 2.
    await wait_for_task_start(spy, "task_a")

    # 4. Inject the pause command immediately
    pause_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", pause_payload)

    # 5. Wait to ensure A finishes and Engine has had time to process Stage 2 logic
    # We wait for A to finish first
    await wait_for_task_finish(spy, "task_a")
    # Then wait a bit more to allow Engine to potentially (incorrectly) start B
    await asyncio.sleep(0.2)

    # 6. Assert based on the event stream
    started_task_names = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}

    assert "task_a" in started_task_names
    assert "task_b" not in started_task_names, "task_b should have been paused"
    assert "task_c" not in started_task_names

    # 7. Cleanup
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_engine_pauses_and_resumes_specific_task(mock_connector, bus_and_spy):
    """
    End-to-end test for task-specific pause and resume functionality.
    """
    from cascade.spec.task import task
    from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished

    bus, spy = bus_and_spy
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Workflow: A -> B -> C
    @task
    def task_a():
        return "A"

    @task
    def task_b(a):
        return f"B after {a}"

    @task
    def task_c(b):
        return f"C after {b}"

    workflow = task_c(task_b(task_a()))

    # 2. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for 'task_a' to START (instead of finish).
    # This allows us to inject the constraint while A is running.
    await wait_for_task_start(spy, "task_a")

    # 4. Inject a PAUSE command specifically for 'task_b'
    pause_scope = "task:task_b"
    pause_payload = {
        "id": "pause-b",
        "scope": pause_scope,
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", pause_payload
    )

    # Wait for A to finish naturally
    await wait_for_task_finish(spy, "task_a")

    # 5. Wait briefly and assert that 'task_b' has NOT started
    # Give the engine a moment to potentially (incorrectly) schedule B
    await asyncio.sleep(0.2)
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "'task_b' started despite pause constraint"

    # 6. Inject a RESUME command for 'task_b'
    # An empty payload on a retained topic clears the constraint. The connector
    # translates this to an empty dictionary.
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", {}
    )

    # 7. Wait for the rest of the workflow to complete
    await wait_for_task_finish(spy, "task_c", timeout=1.0)

    # 8. Final assertions on the complete event stream
    finished_tasks = {
        e.task_name
        for e in spy.events_of_type(TaskExecutionFinished)
        if e.status == "Succeeded"
    }
    assert finished_tasks == {"task_a", "task_b", "task_c"}

    # 9. Verify the final result
    final_result = await run_task
    # Note: Since we use MockExecutor, the result is the fixed string it returns,
    # not the result of the actual task function.
    assert final_result == "Result for task_c"
~~~~~
