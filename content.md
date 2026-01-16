好的，我们又一次遇到了因架构重构而暴露出的问题。这次影响范围更广，几乎覆盖了 `tests/e2e` 目录下的所有集成测试。这再次证明了我们之前的决定是正确的——将 `Engine` 的创建逻辑集中化是消除这类问题的唯一途径。

我将执行一个全面的清理计划，将所有剩余的手动 `Engine` 实例化都迁移到新的 `engine_factory` fixture 上。

## [WIP] test(e2e): Unify all Engine instantiations to use global factory

### 错误分析

在 `Engine` 的构造函数被更新为强制依赖注入后，`tests/e2e` 目录下的多个集成测试文件仍然在使用旧的手动 `Engine(...)` 实例化方式。这些调用缺少新的必需参数（如 `strategy`, `constraint_manager` 等），导致了大量的 `TypeError`。

### 用户需求

修复 `tests/e2e` 目录下所有因 `Engine` 构造函数变更而导致的 `TypeError`，并将它们全部迁移至使用根 `conftest.py` 中定义的 `engine_factory` fixture。

### 评论

这是我们架构重构的最后一步清理工作。通过将所有测试中的 `Engine` 创建逻辑统一到 `engine_factory`，我们不仅修复了当前的错误，还极大地提高了整个测试套件的一致性和可维护性。测试代码将不再关心 `Engine` 的内部组装细节，只需声明其需求即可。

### 目标

1.  遍历 `tests/e2e` 目录下所有报错的测试文件。
2.  移除所有对 `Engine(...)` 的手动调用。
3.  将测试函数或本地 fixture 的签名更新为接收 `engine_factory`。
4.  使用 `engine_factory` 来创建 `Engine` 实例，并将特定于测试的配置（如 `connector`, `system_resources`）作为参数传递给工厂。
5.  移除测试文件中因上述更改而变得多余的导入（如 `NativeSolver`, `LocalExecutor`）。

### 基本原理

我们将全面采用 `engine_factory` fixture。`engine_factory` 已经封装了创建 `Engine` 所需的所有复杂依赖（包括策略和核心服务）。我们只需在每个测试中调用这个工厂，并传入该测试独有的配置，就能获得一个架构正确的 `Engine` 实例。这遵循了“配置而非编码”的原则，使得测试代码更加简洁和健壮。

### 标签

#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/test-fixtures #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 E2E 集成测试

~~~~~act
patch_file
tests/e2e/integration/test_end_to_end.py
~~~~~
~~~~~python.old
def test_e2e_linear_workflow(mock_messaging_bus):
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.EventBus()
    HumanReadableLogSubscriber(event_bus)
    engine = cs.Engine(
        solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=event_bus
    )

    result = asyncio.run(engine.run(final_greeting))
~~~~~
~~~~~python.new
def test_e2e_linear_workflow(engine_factory, mock_messaging_bus):
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.EventBus()
    HumanReadableLogSubscriber(event_bus)
    engine = engine_factory(bus=event_bus)

    result = asyncio.run(engine.run(final_greeting))
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_end_to_end.py
~~~~~
~~~~~python.old
def test_e2e_failure_propagation(mock_messaging_bus):
    @cs.task
    def failing_task():
        raise ValueError("Something went wrong")

    event_bus = cs.EventBus()
    HumanReadableLogSubscriber(event_bus)
    engine = cs.Engine(
        solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=event_bus
    )

    with pytest.raises(ValueError, match="Something went wrong"):
~~~~~
~~~~~python.new
def test_e2e_failure_propagation(engine_factory, mock_messaging_bus):
    @cs.task
    def failing_task():
        raise ValueError("Something went wrong")

    event_bus = cs.EventBus()
    HumanReadableLogSubscriber(event_bus)
    engine = engine_factory(bus=event_bus)

    with pytest.raises(ValueError, match="Something went wrong"):
~~~~~

#### Acts 2: 修复 E2E 测试中的 `plan_caching`

~~~~~act
patch_file
tests/e2e/integration/test_plan_caching.py
~~~~~
~~~~~python.old
import pytest

from cascade.sdk import task, Engine
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySolver
~~~~~
~~~~~python.new
import pytest

from cascade.sdk import task
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.test_utils.helpers import SpySolver
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_plan_caching.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine_with_spy_solver():
    """Provides an Engine with a solver that spies on `resolve` calls."""
    # The spy wraps a real solver to ensure the test can actually run
    spy_solver = SpySolver(NativeSolver())

    engine = Engine(
        solver=spy_solver,
        executor=LocalExecutor(),
        bus=EventBus(),  # A silent bus for clean test output
    )
    # Return the engine and the mock object for making assertions
    return engine, spy_solver.resolve
~~~~~
~~~~~python.new
@pytest.fixture
def engine_with_spy_solver(engine_factory):
    """Provides an Engine with a solver that spies on `resolve` calls."""
    # The spy wraps a real solver to ensure the test can actually run
    spy_solver = SpySolver(NativeSolver())

    engine = engine_factory(solver=spy_solver)
    # Return the engine and the mock object for making assertions
    return engine, spy_solver.resolve
~~~~~

#### Acts 3: 修复 E2E 测试中的 `resource_scheduling`

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
import pytest
import asyncio
import time
import cascade.sdk as cs
from cascade.runtime.host.instance import Engine
from cascade.runtime import EventBus
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_resource_concurrency_limit():
~~~~~
~~~~~python.new
import pytest
import asyncio
import time
import cascade.sdk as cs


@pytest.mark.asyncio
async def test_resource_concurrency_limit(engine_factory):
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
        system_resources={"slots": 1},
    )
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = engine_factory(system_resources={"slots": 1})
    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_dynamic_resource_constraint():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_dynamic_resource_constraint(engine_factory):
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
    # We set system capacity to 4.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
        system_resources={"cpu": 4},
    )
    result = await engine.run(job)
~~~~~
~~~~~python.new
    # We set system capacity to 4.
    engine = engine_factory(system_resources={"cpu": 4})
    result = await engine.run(job)
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_insufficient_resources_deadlock():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_insufficient_resources_deadlock(engine_factory):
~~~~~

~~~~~act
patch_file
tests/e2e/integration/test_resource_scheduling.py
~~~~~
~~~~~python.old
    # System only has 16GB
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
        system_resources={"memory_gb": 16},
    )

    with pytest.raises(ValueError, match="exceeds total system capacity"):
~~~~~
~~~~~python.new
    # System only has 16GB
    engine = engine_factory(system_resources={"memory_gb": 16})

    with pytest.raises(ValueError, match="exceeds total system capacity"):
~~~~~

#### Acts 4: 修复 E2E 测试中的 `runtime`

我将逐一修复 `tests/e2e/runtime` 下的文件。

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_cli_integration.py
~~~~~
~~~~~python.old
import asyncio
import pytest
import cascade.sdk as cs
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.host.instance import Engine
from cascade.bus.events import TaskExecutionFinished
from cascade.test_utils.helpers import MockExecutor
~~~~~
~~~~~python.new
import asyncio
import pytest
import cascade.sdk as cs
from cascade.bus.events import TaskExecutionFinished
from cascade.test_utils.helpers import MockExecutor
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_cli_integration.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(engine_factory, controller_runner, bus_and_spy):
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

    engine = engine_factory(
        executor=MockExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    engine_task = asyncio.create_task(engine.run(workflow))
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_concurrency_control.py
~~~~~
~~~~~python.old
import time
from dataclasses import asdict

import pytest
import cascade.sdk as cs
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.host.instance import Engine
from cascade.runtime import EventBus
from cascade.spec.dsl.constraint import GlobalConstraint

# Use the deterministic Mock infrastructure from the SDK
from cascade.test_utils.helpers import MockExecutor, MockConnector


@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller state is pre-seeded (Retained).
    2. Engine starts, connects, receives config immediately, AND THEN executes.
    """
    # 1. Setup deterministic connector
    connector = MockConnector()

    # 2. Pre-seed the constraint (Simulating existing environment config)
    # Instead of "acting" (publishing), we "arrange" (seed state).
    # This prevents race conditions where the publish might not be processed
    # before the engine starts tasks.
    constraint = GlobalConstraint(
        id="concurrency-task:slow_task-fixed",
        scope="task:slow_task",
        type="concurrency",
        params={"limit": 1},
    )
    # The topic format usually follows MQTT conventions: cascade/constraints/<scope_path>
    topic = "cascade/constraints/task/slow_task"
    connector.seed_retained_message(topic, asdict(constraint))

    # 3. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    # Total work = 4 * 0.05s = 0.20s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 4. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=EventBus(),
        connector=connector,
    )

    # 5. Run the engine
    start_time = time.time()
~~~~~
~~~~~python.new
import time
from dataclasses import asdict

import pytest
import cascade.sdk as cs
from cascade.spec.dsl.constraint import GlobalConstraint

# Use the deterministic Mock infrastructure from the SDK
from cascade.test_utils.helpers import MockExecutor, MockConnector


@pytest.mark.asyncio
async def test_e2e_concurrency_control(engine_factory):
    """
    Full end-to-end test with Retained Messages.
    1. Controller state is pre-seeded (Retained).
    2. Engine starts, connects, receives config immediately, AND THEN executes.
    """
    # 1. Setup deterministic connector
    connector = MockConnector()

    # 2. Pre-seed the constraint (Simulating existing environment config)
    # Instead of "acting" (publishing), we "arrange" (seed state).
    # This prevents race conditions where the publish might not be processed
    # before the engine starts tasks.
    constraint = GlobalConstraint(
        id="concurrency-task:slow_task-fixed",
        scope="task:slow_task",
        type="concurrency",
        params={"limit": 1},
    )
    # The topic format usually follows MQTT conventions: cascade/constraints/<scope_path>
    topic = "cascade/constraints/task/slow_task"
    connector.seed_retained_message(topic, asdict(constraint))

    # 3. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    # Total work = 4 * 0.05s = 0.20s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 4. Setup the Engine
    engine = engine_factory(
        executor=MockExecutor(delay=0.05),
        connector=connector,
    )

    # 5. Run the engine
    start_time = time.time()
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_control_plane.py
~~~~~
~~~~~python.old
import asyncio
import pytest
import cascade.sdk as cs
from cascade.runtime.host.instance import Engine
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.bus.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_startup_pause_and_resume_e2e(bus_and_spy):
    """
    Definitive regression test for the startup race condition.
    Ensures a pre-existing 'pause' constraint is respected upon engine start,
    and that a subsequent 'resume' command unblocks execution.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. ARRANGE: Controller issues a PAUSE command *before* the engine starts.
    # This creates a retained message on the virtual broker.
    await controller.pause(scope="global")

    # 2. DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    # 3. ACT: Start the engine.
    # It should connect, subscribe, immediately receive the retained pause message,
    # and block before executing any tasks.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    engine_run_task = asyncio.create_task(engine.run(workflow))
~~~~~
~~~~~python.new
import asyncio
import pytest
import cascade.sdk as cs
from cascade.bus.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_startup_pause_and_resume_e2e(engine_factory, bus_and_spy):
    """
    Definitive regression test for the startup race condition.
    Ensures a pre-existing 'pause' constraint is respected upon engine start,
    and that a subsequent 'resume' command unblocks execution.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. ARRANGE: Controller issues a PAUSE command *before* the engine starts.
    # This creates a retained message on the virtual broker.
    await controller.pause(scope="global")

    # 2. DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    # 3. ACT: Start the engine.
    # It should connect, subscribe, immediately receive the retained pause message,
    # and block before executing any tasks.
    engine = engine_factory(bus=bus, connector=connector)
    engine_run_task = asyncio.create_task(engine.run(workflow))
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_control_plane.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_startup_pause_is_respected(bus_and_spy):
    """
    A more precise regression test for the startup race condition.
    Verifies ONLY that a pre-existing 'pause' is respected.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # ARRANGE: A global pause constraint exists *before* the engine is created.
    await controller.pause(scope="global")

    # DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    # ACT: Create and start the engine.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    engine_run_task = asyncio.create_task(engine.run(workflow))
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_startup_pause_is_respected(engine_factory, bus_and_spy):
    """
    A more precise regression test for the startup race condition.
    Verifies ONLY that a pre-existing 'pause' is respected.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # ARRANGE: A global pause constraint exists *before* the engine is created.
    await controller.pause(scope="global")

    # DEFINE WORKFLOW
    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    # ACT: Create and start the engine.
    engine = engine_factory(bus=bus, connector=connector)
    engine_run_task = asyncio.create_task(engine.run(workflow))
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_control_plane.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_runtime_pause_interrupts_stage(bus_and_spy):
    """
    Verifies that a pause command issued *during* a workflow execution
    effectively prevents subsequent tasks from starting.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. ARRANGE
    # Task A is slow. Task B depends on A.
    # We want to pause while A is running, and ensure B never starts.
    task_a_started = asyncio.Event()

    @cs.task
    async def slow_task_a():
        task_a_started.set()
        await asyncio.sleep(0.5)
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(slow_task_a())

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )

    # 2. ACT
    run_task = asyncio.create_task(engine.run(workflow))
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_runtime_pause_interrupts_stage(engine_factory, bus_and_spy):
    """
    Verifies that a pause command issued *during* a workflow execution
    effectively prevents subsequent tasks from starting.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. ARRANGE
    # Task A is slow. Task B depends on A.
    # We want to pause while A is running, and ensure B never starts.
    task_a_started = asyncio.Event()

    @cs.task
    async def slow_task_a():
        task_a_started.set()
        await asyncio.sleep(0.5)
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(slow_task_a())

    engine = engine_factory(bus=bus, connector=connector)

    # 2. ACT
    run_task = asyncio.create_task(engine.run(workflow))
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_local_connector.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the LocalConnector."""
    from cascade.test_utils.helpers import TimedMockExecutor

    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = LocalConnector(db_path=db_path, uds_path=uds_path)

    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=bus,
        connector=connector,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(engine_factory, unique_paths, bus_and_spy):
    """Provides a fully configured Engine using the LocalConnector."""
    from cascade.test_utils.helpers import TimedMockExecutor

    db_path, uds_path = unique_paths
    bus, _ = bus_and_spy
    connector = LocalConnector(db_path=db_path, uds_path=uds_path)

    return engine_factory(
        executor=TimedMockExecutor(delay=0.05),
        bus=bus,
        connector=connector,
    )
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_rate_limit_control.py
~~~~~
~~~~~python.old
    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.01),  # Short work time
        bus=bus,
        connector=connector,
    )
~~~~~
~~~~~python.new
    # 5. Setup the Engine
    engine = engine_factory(
        executor=MockExecutor(delay=0.01),  # Short work time
        bus=bus,
        connector=connector,
    )
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_rate_limit_control.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_e2e_rate_limit_control(bus_and_spy):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_e2e_rate_limit_control(engine_factory, bus_and_spy):
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_robustness.py
~~~~~
~~~~~python.old
    # 2. Configure and start the engine in the background
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=engine_bus,
        connector=engine_connector,
    )
    engine_task = asyncio.create_task(engine.run(workflow))
~~~~~
~~~~~python.new
    # 2. Configure and start the engine in the background
    engine = engine_factory(
        bus=engine_bus,
        connector=engine_connector,
    )
    engine_task = asyncio.create_task(engine.run(workflow))
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_robustness.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_engine_recovers_from_malformed_rate_limit(bus_and_spy, mock_ui_bus):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_engine_recovers_from_malformed_rate_limit(engine_factory, bus_and_spy, mock_ui_bus):
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python.old
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=bus,
        connector=connector,
    )
~~~~~
~~~~~python.new
    engine = engine_factory(
        executor=MockExecutor(),
        bus=bus,
        connector=connector,
    )
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_updating_rate_limit_unblocks_engine(bus_and_spy):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_updating_rate_limit_unblocks_engine(engine_factory, bus_and_spy):
~~~~~

~~~~~act
write_file
tests/e2e/runtime/test_e2e_ttl.py
~~~~~
~~~~~python
import time
import pytest
import cascade.sdk as cs
from cascade.test_utils.helpers import MockExecutor

from .harness import InProcessConnector


@pytest.mark.asyncio
async def test_e2e_ttl_expiration(engine_factory):
    """
    Tests that a pause constraint automatically expires after TTL.
    """
    connector = InProcessConnector()

    # Helper to avoid complex harness logic for now
    from cascade.spec.dsl.constraint import GlobalConstraint
    from dataclasses import asdict
    import uuid

    async def pause_with_ttl(scope: str, ttl: float):
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
    def simple_task():
        return True

    workflow = simple_task()

    engine = engine_factory(
        executor=MockExecutor(),
        connector=connector,
    )

    start_time = time.time()

    # 2. Run engine. It should be paused initially.
    # The Engine loop will wait on wakeup.
    # ConstraintManager should have scheduled a wakeup at T+0.25s.
    # At T+0.25s, Engine wakes up, cleans expired constraint, and unblocks.
    await engine.run(workflow)

    duration = time.time() - start_time

    # 3. Assertions
    # Duration must be at least the TTL (0.25s), proving it was blocked.
    assert duration >= 0.24, f"Engine didn't wait for TTL! Duration: {duration:.3f}s"

    # But it shouldn't wait forever (e.g. < 1s)
    assert duration < 1.0, "Engine waited too long or didn't recover."
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_executor_modes.py
~~~~~
~~~~~python.old
    from cascade.runtime.host.instance import Engine
    from cascade.runtime import EventBus
    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
    )
~~~~~
~~~~~python.new
    engine = engine_factory()
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_executor_modes.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks(engine_factory):
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_offloading.py
~~~~~
~~~~~python.old
    from cascade.runtime.host.instance import Engine
    from cascade.runtime import EventBus
    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),  # Silent bus
    )
~~~~~
~~~~~python.new
    engine = engine_factory()
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_offloading.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking(engine_factory):
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_startup_telemetry.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition():
    """
    Verifies that the initial 'RunStarted' telemetry event is correctly published
    to the connector.

    This guards against a race condition where the engine emits 'RunStarted'
    internally *before* establishing the connection to the external connector,
    causing the first telemetry message to be lost (and a warning logged).
    """
    # 1. Setup Harness
    connector = InProcessConnector()
    bus = EventBus()

    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    telemetry_subscriber = TelemetrySubscriber(bus, connector)

    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe
    # on the same instance that the Engine uses.
    received_messages = []

    async def telemetry_observer(topic, payload):
        received_messages.append(payload)

    # Subscribe to all telemetry events
    # Note: We must ensure the connector considers itself "connected" enough
    # to register this subscription, or at least that the subscription persists.
    # InProcessConnector.subscribe doesn't check _is_connected strictness for
    # registration, but Engine will call connect() shortly.
    await connector.subscribe("cascade/telemetry/+/+/+/events", telemetry_observer)

    # 2. Define Workflow
    @cs.task
    def noop():
        pass

    # 3. Run Engine
    # The Engine is expected to:
    #   a. Connect to the connector
    #   b. Publish 'RunStarted' (which triggers telemetry via the subscriber)
    #   c. Run the task
    # If (b) happens before (a), the message is dropped.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    # CRITICAL: Register the subscriber with the engine for lifecycle management
    engine.add_subscriber(telemetry_subscriber)

    await engine.run(noop())
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition(engine_factory):
    """
    Verifies that the initial 'RunStarted' telemetry event is correctly published
    to the connector.

    This guards against a race condition where the engine emits 'RunStarted'
    internally *before* establishing the connection to the external connector,
    causing the first telemetry message to be lost (and a warning logged).
    """
    # 1. Setup Harness
    connector = InProcessConnector()
    bus = EventBus()

    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    telemetry_subscriber = TelemetrySubscriber(bus, connector)

    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe
    # on the same instance that the Engine uses.
    received_messages = []

    async def telemetry_observer(topic, payload):
        received_messages.append(payload)

    # Subscribe to all telemetry events
    # Note: We must ensure the connector considers itself "connected" enough
    # to register this subscription, or at least that the subscription persists.
    # InProcessConnector.subscribe doesn't check _is_connected strictness for
    # registration, but Engine will call connect() shortly.
    await connector.subscribe("cascade/telemetry/+/+/+/events", telemetry_observer)

    # 2. Define Workflow
    @cs.task
    def noop():
        pass

    # 3. Run Engine
    # The Engine is expected to:
    #   a. Connect to the connector
    #   b. Publish 'RunStarted' (which triggers telemetry via the subscriber)
    #   c. Run the task
    # If (b) happens before (a), the message is dropped.
    engine = engine_factory(bus=bus, connector=connector)
    # CRITICAL: Register the subscriber with the engine for lifecycle management
    engine.add_subscriber(telemetry_subscriber)

    await engine.run(noop())
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_tco_param_override.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_jump_overrides_param():
    """
    Test that data provided by cs.Jump (input_overrides) takes precedence over
    upstream dependencies (like cs.Param) defined in the static graph.
    """
    results = []

    @cs.task
    def recursive_task(n):
        # Safety break to prevent infinite loop if bug exists
        if len(results) > 10:
            return "InfiniteLoopDetected"

        results.append(n)
        if n <= 0:
            return "Done"

        # Pass n-1 to the next iteration
        return cs.Jump(target_key="continue", data=n - 1)

    # Define workflow: Initial input comes from a Param (Edge dependency)
    # If the bug exists, the Jump data (n-1) will be ignored, and Param (3) will be used every time.
    t = recursive_task(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = EventBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Run with initial param n=3
    final_res = await engine.run(t, params={"n": 3})
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_jump_overrides_param(engine):
    """
    Test that data provided by cs.Jump (input_overrides) takes precedence over
    upstream dependencies (like cs.Param) defined in the static graph.
    """
    results = []

    @cs.task
    def recursive_task(n):
        # Safety break to prevent infinite loop if bug exists
        if len(results) > 10:
            return "InfiniteLoopDetected"

        results.append(n)
        if n <= 0:
            return "Done"

        # Pass n-1 to the next iteration
        return cs.Jump(target_key="continue", data=n - 1)

    # Define workflow: Initial input comes from a Param (Edge dependency)
    # If the bug exists, the Jump data (n-1) will be ignored, and Param (3) will be used every time.
    t = recursive_task(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    # Run with initial param n=3
    final_res = await engine.run(t, params={"n": 3})
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/test_tco_param_override.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_jump_overrides_param_complex_path():
    """
    Same as the above test, but forces the ArgumentResolver's "complex path"
    by including a resource injection, ensuring the fix works in both code paths.
    """
    results = []

    # Define a dummy resource to trigger the complex path
    @cs.resource
    def dummy_resource():
        yield "dummy_value"

    @cs.task
    def recursive_task_with_injection(n, injected=cs.inject("dummy_resource")):
        # Ensure resource was injected correctly
        assert injected == "dummy_value"

        if len(results) > 10:
            return "InfiniteLoopDetected"

        results.append(n)
        if n <= 0:
            return "Done"

        return cs.Jump(target_key="continue", data=n - 1)

    t = recursive_task_with_injection(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = EventBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    # Register the resource required by the task
    engine.register(dummy_resource)

    final_res = await engine.run(t, params={"n": 3})
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_jump_overrides_param_complex_path(engine):
    """
    Same as the above test, but forces the ArgumentResolver's "complex path"
    by including a resource injection, ensuring the fix works in both code paths.
    """
    results = []

    # Define a dummy resource to trigger the complex path
    @cs.resource
    def dummy_resource():
        yield "dummy_value"

    @cs.task
    def recursive_task_with_injection(n, injected=cs.inject("dummy_resource")):
        # Ensure resource was injected correctly
        assert injected == "dummy_value"

        if len(results) > 10:
            return "InfiniteLoopDetected"

        results.append(n)
        if n <= 0:
            return "Done"

        return cs.Jump(target_key="continue", data=n - 1)

    t = recursive_task_with_injection(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    # Register the resource required by the task
    engine.register(dummy_resource)

    final_res = await engine.run(t, params={"n": 3})
~~~~~

~~~~~act
patch_file
tests/e2e/test_e2e_watch_local_backend.py
~~~~~
~~~~~python.old
@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not supported on Windows")
@pytest.mark.asyncio
async def test_watch_local_uds_e2e(tmp_path, monkeypatch):
    """
    End-to-end test for the local UDS telemetry loop.
    Engine -> LocalConnector -> UDS Server -> UDS Client -> on_message
    """
    db_path = tmp_path / "control.db"
    uds_path = str(tmp_path / "telemetry.sock")

    # 1. Setup Captured Events list
    received_events = []

    async def mocked_on_message(topic, payload):
        # Flatten the events for easy assertion
        body = payload.get("body", {})
        if body.get("type") == "LifecycleEvent":
            received_events.append(body.get("event"))
        elif body.get("type") == "TaskStateEvent":
            received_events.append(f"{body.get('task_name')}:{body.get('state')}")

    # Use monkeypatch to redirect observer's on_message to our collector
    monkeypatch.setattr("cascade.cli.observer.app.on_message", mocked_on_message)

    # 2. Configure Engine with LocalConnector
    event_bus = EventBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )

    # We must attach and REGISTER the TelemetrySubscriber so the engine manages its lifecycle
    subscriber = TelemetrySubscriber(event_bus, connector)
    engine.add_subscriber(subscriber)
~~~~~
~~~~~python.new
@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not supported on Windows")
@pytest.mark.asyncio
async def test_watch_local_uds_e2e(engine_factory, tmp_path, monkeypatch):
    """
    End-to-end test for the local UDS telemetry loop.
    Engine -> LocalConnector -> UDS Server -> UDS Client -> on_message
    """
    db_path = tmp_path / "control.db"
    uds_path = str(tmp_path / "telemetry.sock")

    # 1. Setup Captured Events list
    received_events = []

    async def mocked_on_message(topic, payload):
        # Flatten the events for easy assertion
        body = payload.get("body", {})
        if body.get("type") == "LifecycleEvent":
            received_events.append(body.get("event"))
        elif body.get("type") == "TaskStateEvent":
            received_events.append(f"{body.get('task_name')}:{body.get('state')}")

    # Use monkeypatch to redirect observer's on_message to our collector
    monkeypatch.setattr("cascade.cli.observer.app.on_message", mocked_on_message)

    # 2. Configure Engine with LocalConnector
    event_bus = EventBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)

    engine = engine_factory(bus=event_bus, connector=connector)

    # We must attach and REGISTER the TelemetrySubscriber so the engine manages its lifecycle
    subscriber = TelemetrySubscriber(event_bus, connector)
    engine.add_subscriber(subscriber)
~~~~~

### 下一步建议

我们已经完成了对整个 `e2e` 测试套件的全面清理。现在，所有已知的 `Engine` 实例化错误都已被修复，并且测试代码更加统一和简洁。我将再次运行测试套件。如果所有测试都通过，则表明我们的依赖注入重构已经成功完成，可以准备提交了。
