## [WIP] fix: 使用 NativeSolver 修复集成测试中的依赖错误

### 错误分析
`DependencyMissingError` 的根本原因是测试中使用的 `MockSolver` 实现过于简单。它将所有节点（无论是否存在依赖关系）都放置在同一个执行阶段（Stage）中。

在 Cascade 的执行模型中，同一阶段内的节点被认为是相互独立且可并行的。当 `Engine` 处理 A -> B -> C 这样的依赖链时，如果它们都在同一阶段：
1.  `Engine` 尝试并行处理它们。
2.  当轮到处理 B 或 C 时，`ArgumentResolver` 会尝试获取其上游依赖（A 或 B）的结果。
3.  由于 `MockSolver` 错误地暗示它们可以并行，上游任务可能尚未执行完毕（或在本例中，B 被暂停了）。
4.  因此，`StateBackend` 中没有结果，导致抛出 `DependencyMissingError`。

### 用户需求
修复测试错误，确保集成测试能够正确处理任务间的依赖关系。

### 评论
这个错误凸显了在集成测试中使用真实组件的重要性。`Solver` 的核心职责就是正确地对图进行拓扑排序和分层。在涉及依赖关系的测试中，Mock 这个行为极其容易出错。改用真实的 `NativeSolver` 不仅修复了错误，也增加了测试的真实性。

### 目标
1.  重写 `tests/py/runtime/test_engine_constraints.py`。
2.  移除 `MockSolver`。
3.  引入 `cascade.adapters.solvers.native.NativeSolver`。
4.  在所有测试 fixture 和用例中，使用 `NativeSolver` 替代 `MockSolver`。
5.  保留 `MockConnector` 中关于通配符匹配的修复逻辑。

### 基本原理
`NativeSolver` 会根据依赖关系正确地将 A, B, C 分配到不同的阶段（Stage 1: [A], Stage 2: [B], Stage 3: [C]）。
当测试运行时：
1.  Stage 1 (A) 完成。
2.  进入 Stage 2 (B)。
3.  暂停指令生效，B 被挂起。
4.  由于 Stage 2 尚未完成，Engine 永远不会尝试进入 Stage 3 (C)。
5.  这样就避免了在 B 未完成时尝试解析 C 的参数，从而消除了 `DependencyMissingError`。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/runtime #concept/scheduler
#ai/instruct
#task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重写测试文件

~~~~~act
write_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
import asyncio
from typing import Callable, Awaitable, Dict, Any

import pytest

from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.spec.constraint import GlobalConstraint


# --- Test Fixtures and Mocks ---

class MockConnector(Connector):
    """A mock connector for testing Engine's subscription logic."""

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self.connected = False
        self.disconnected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        pass  # Not needed for this test

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message."""
        # Check all subscriptions for a match
        for sub_topic, callback in self.subscriptions.items():
            is_match = False
            if sub_topic == topic:
                is_match = True
            elif sub_topic.endswith("/#"):
                prefix = sub_topic[:-2]
                if topic.startswith(prefix):
                    is_match = True
            
            if is_match:
                await callback(topic, payload)


class MockExecutor(Executor):
    async def execute(self, node, args, kwargs):
        return f"Result for {node.name}"


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
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
async def test_engine_updates_constraints_on_message(engine_with_connector, mock_connector):
    """
    Verify that the Engine's ConstraintManager is updated when a valid message is received.
    """
    from cascade.spec.task import task

    @task
    def dummy_task():
        pass

    # Start the run to establish subscriptions
    run_task = asyncio.create_task(engine_with_connector.run(dummy_task()))

    # Give the engine a moment to start and subscribe
    await asyncio.sleep(0.01)

    # Simulate receiving a constraint message
    constraint_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", constraint_payload)

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
    await asyncio.sleep(0.01)

    # Payload missing the required 'id' key
    malformed_payload = {
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", malformed_payload)

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
        executor=MockExecutor(),
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

    # 3. Wait for the first task to complete
    await wait_for_task_finish(spy, "task_a")

    # 4. Inject the pause command
    pause_payload = {
        "id": "global-pause",
        "scope": "global",
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message("cascade/constraints/control", pause_payload)

    # 5. Wait a moment to see if the engine schedules the next task
    await asyncio.sleep(0.2)  # Longer than engine's internal sleep

    # 6. Assert based on the event stream
    started_task_names = {
        e.task_name for e in spy.events_of_type(TaskExecutionStarted)
    }

    assert "task_a" in started_task_names
    assert "task_b" not in started_task_names, "task_b should have been paused"
    assert "task_c" not in started_task_names

    # 7. Cleanup
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass
~~~~~
