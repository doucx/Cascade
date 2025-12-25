很好，我们已经完成了核心协议 mock 的整合。现在，我们来处理最后一类——行为特化的 `Executor` 替身。

根据我们最初的分析，有三个分散的、用于模拟特定执行行为的 `Executor` 实现：`MockWorkExecutor`, `SlowWorkExecutor`, 和 `TimingWorkExecutor`。我们的通用 `cascade.testing.MockExecutor` 已经足够强大，可以完全取代它们。

这个计划将完成这项最后的整合工作，并在这个过程中顺便提升一个测试用例的健壮性。

## [WIP] refactor: 使用 MockExecutor 统一所有行为型测试替身

### 用户需求
将所有用于模拟特定行为（如延迟、计时）的 `Executor` 实现 (`MockWorkExecutor`, `SlowWorkExecutor`, `TimingWorkExecutor`) 替换为 `cascade.testing` 中统一的 `MockExecutor`。

### 评论
这是对测试基础设施进行标准化的收官之战。通过这次重构，我们将彻底消除所有重复的 `Executor` 测试辅助类，确保所有相关测试都依赖于一个统一的、行为可预测的来源。这不仅能让代码库更整洁，也使得未来的测试编写工作更加简单。

### 目标
1.  重构 `tests/e2e/runtime/harness.py`，移除 `MockWorkExecutor`。
2.  重构 `tests/e2e/runtime/test_e2e_cli_integration.py`，使其使用通用的 `MockExecutor`。
3.  重构 `tests/e2e/runtime/test_e2e_concurrency_control.py`，用 `MockExecutor(delay=0.05)` 替换本地的 `SlowWorkExecutor`。
4.  重构 `tests/e2e/runtime/test_e2e_rate_limit_control.py`，用 `MockExecutor` 替换 `TimingWorkExecutor`，并改进其测试逻辑，通过事件总线 (`MessageBus` 和 `SpySubscriber`) 来断言任务完成的时间，而不是依赖 `Executor` 的返回值。

### 基本原理
我们将逐一替换这些特化的 `Executor`。对于 `MockWorkExecutor` 和 `SlowWorkExecutor`，这是一个直接的替换。对于 `TimingWorkExecutor`，情况稍微复杂，因为它被设计为返回任务的完成时间戳。与其让通用的 `MockExecutor` 支持这个特例，不如遵循“验证意图而非实现”的原则，改进测试本身。我们将修改 `test_e2e_rate_limit_control`，让它通过监听 `TaskExecutionFinished` 事件来获取任务的完成时间。这是一种更健壮的测试模式，因为它直接观察系统的外部行为（事件），而不是依赖一个内部组件（Executor）的特定返回值。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-doubles #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 移除 `harness.py` 中的 `MockWorkExecutor`

首先，我们清理测试工具集 `harness.py`，移除现在已经冗余的 `MockWorkExecutor`。

~~~~~act
write_file
tests/e2e/runtime/harness.py
~~~~~
~~~~~python
import asyncio
from typing import Dict, Any, List
import uuid
from dataclasses import asdict

from cascade.connectors.local import LocalBusConnector
from cascade.spec.protocols import Connector, Executor
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally.
InProcessConnector = LocalBusConnector


class ControllerTestApp:
    """A lightweight simulator for the cs-controller CLI tool."""

    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause(self, scope: str = "global"):
        constraint = GlobalConstraint(
            id=f"pause-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="pause",
            params={},
        )
        await self._publish(scope, constraint)

    async def resume(self, scope: str = "global"):
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        # Sending an empty dict simulates the connector's behavior for an empty payload
        await self.connector.publish(topic, {}, retain=True)

    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)
~~~~~

#### Acts 2: 更新 CLI 集成测试以使用 `MockExecutor`

接着，我们更新 `test_e2e_cli_integration.py`，使其从 `cascade.testing` 导入并使用 `MockExecutor`。

~~~~~act
write_file
tests/e2e/runtime/test_e2e_cli_integration.py
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionFinished
from cascade.testing import MockExecutor

# 导入 app 模块中的核心异步逻辑函数
from cascade.cli.controller import app as controller_app

from .harness import InProcessConnector

# --- Test Harness for In-Process CLI Interaction ---


class SharedInstanceConnector:
    """
    Wraps an InProcessConnector to prevent 'disconnect' calls from affecting
    the underlying shared instance. This allows the Engine to stay connected
    even when the short-lived CLI command 'disconnects'.
    """

    def __init__(self, delegate: InProcessConnector):
        self._delegate = delegate

    async def connect(self):
        # Ensure the underlying connector is active
        await self._delegate.connect()

    async def disconnect(self):
        # CRITICAL: Ignore disconnects from the CLI.
        # Since we share the single InProcessConnector instance with the Engine,
        # checking out would kill the Engine's subscription loop too.
        pass

    async def publish(self, *args, **kwargs):
        await self._delegate.publish(*args, **kwargs)

    async def subscribe(self, *args, **kwargs):
        await self._delegate.subscribe(*args, **kwargs)


class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""

    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
        backend: str = "mqtt",
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            backend=backend,
            hostname="localhost",  # Constant for test purposes
            port=1883,  # Constant for test purposes
        )


@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    # 1. Create the master connector that holds the state (topics, queues)
    master_connector = InProcessConnector()

    # 2. Create a wrapper for the CLI that won't close the master connector
    cli_connector_wrapper = SharedInstanceConnector(master_connector)

    # 3. Patch the CLI app to use our wrapper
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: cli_connector_wrapper,
    )

    # 4. Return the controller initialized with the MASTER connector
    #    (The Engine will use this master connector directly)
    return InProcessController(master_connector)


# --- The Failing Test Case ---


@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(controller_runner, bus_and_spy):
    """
    This test is EXPECTED TO FAIL with a timeout on the pre-fix codebase.
    It verifies that a non-idempotent CLI controller creates conflicting
    constraints that deadlock the engine. After the fix is applied, this
    test should pass.
    """
    bus, spy = bus_and_spy

    @cs.task
    def fast_task(i: int):
        return i

    workflow = fast_task.map(i=range(10))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit.
        await controller_runner.set_limit(scope="global", rate="1/s")

        # 2. Wait to confirm the engine is throttled.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break

        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. The bug causes this to ADD a new conflicting constraint.
        await controller_runner.set_limit(scope="global", rate="100/s")

        # 4. The engine should now finish quickly. The bug will cause a timeout here.
        await asyncio.wait_for(engine_task, timeout=2.0)

    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task

    # This part is only reached if the test passes (i.e., after the bug is fixed).
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10
~~~~~

#### Acts 3: 更新并发控制测试

然后，我们重构 `test_e2e_concurrency_control.py`，用 `MockExecutor` 替换 `SlowWorkExecutor`。

~~~~~act
write_file
tests/e2e/runtime/test_e2e_concurrency_control.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Dict, Any, List
import uuid
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockExecutor

from .harness import InProcessConnector


@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller publishes constraint (Retained).
    2. Engine starts, connects, receives config, AND THEN executes.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()

    # 2. Setup the Controller (simulated by manual publish helper in this test context if needed,
    # or using the simplified helper from harness but constructing payload manually as in original test)
    # The ControllerTestApp in harness is generic. We can extend it or use it.
    # The original test had set_concurrency_limit helper. Let's replicate or inline it.

    # Inline setting concurrency limit using standard controller app logic
    # But wait, harness ControllerTestApp only has pause/resume.
    # Let's use the connector directly or update harness later?
    # To keep this atomic, I'll just publish via connector here or extend ControllerTestApp locally if needed.
    # Actually, let's just do manual publish to keep it simple as in harness.

    # To avoid changing harness too much in Acts 1, I will implement helper here.
    from cascade.spec.constraint import GlobalConstraint

    async def set_concurrency_limit(scope: str, limit: int):
        constraint = GlobalConstraint(
            id=f"concurrency-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="concurrency",
            params={"limit": limit},
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 3. Publish the constraint FIRST (Simulating existing environment config)
    # Limit task concurrency to 1
    await set_concurrency_limit(scope="task:slow_task", limit=1)

    # 4. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=connector,
    )

    # 6. Run the engine
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s.
    assert duration >= 0.18, (
        f"Expected serial execution (~0.2s), but took {duration:.4f}s"
    )
~~~~~

#### Acts 4: 更新速率限制测试并改进其断言逻辑

最后，我们重构 `test_e2e_rate_limit_control.py`，用 `MockExecutor` 替换 `TimingWorkExecutor`，并引入 `SpySubscriber` 来进行更可靠的时间断言。

~~~~~act
write_file
tests/e2e/runtime/test_e2e_rate_limit_control.py
~~~~~
~~~~~python
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished
from cascade.testing import MockExecutor, SpySubscriber

from .harness import InProcessConnector


@pytest.mark.asyncio
async def test_e2e_rate_limit_control(bus_and_spy):
    """
    Full end-to-end test for rate limiting.
    1. Controller publishes a rate limit constraint (Retained).
    2. Engine starts, receives the constraint, and throttles execution.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()
    bus, spy = bus_and_spy

    # 2. Setup Helper (Inline to avoid complex harness changes for now)
    from cascade.spec.constraint import GlobalConstraint
    from dataclasses import asdict
    import uuid

    async def set_rate_limit(scope: str, rate: str, capacity: float = None):
        params = {"rate": rate}
        if capacity is not None:
            params["capacity"] = capacity

        constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="rate_limit",
            params=params,
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 3. Publish the constraint FIRST.
    # Limit to 5 tasks/sec (1 every 0.2s), with a burst capacity of 2.
    await set_rate_limit(scope="task:fast_task", rate="5/s", capacity=2)

    # 4. Define the workflow
    @cs.task
    def fast_task():
        return  # Does almost nothing

    # 4 tasks that should be rate-limited
    workflow = fast_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.01),  # Short work time
        bus=bus,
        connector=connector,
    )

    # 6. Run the engine
    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions based on event timestamps
    finished_events = spy.events_of_type(TaskExecutionFinished)
    assert len(finished_events) == 4

    finish_times = sorted([e.timestamp - start_time for e in finished_events])

    # Expected timing:
    # - Capacity=2, so Task 1 & 2 run immediately in the first 0.01s slot.
    # - Rate=5/s -> 1 token refills every 0.2s.
    # - T=0.01s: T1, T2 finish. Bucket is empty.
    # - T=0.20s: 1 token available. T3 starts.
    # - T=0.21s: T3 finishes.
    # - T=0.40s: 1 token available. T4 starts.
    # - T=0.41s: T4 finishes.
    # Total duration should be ~0.4s. Without rate limit, it's ~0.01s.

    assert duration >= 0.38, (
        f"Expected throttled execution (~0.4s), but took {duration:.4f}s"
    )

    # Check the timestamps to verify sequential execution after burst
    # First two should be very close together
    assert finish_times[1] - finish_times[0] < 0.05
    # Gap between 2nd and 3rd should be ~0.2s
    assert finish_times[2] - finish_times[1] > 0.18
    # Gap between 3rd and 4th should be ~0.2s
    assert finish_times[3] - finish_times[2] > 0.18
~~~~~
