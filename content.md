大规模重构 `Engine` 构造函数带来的连锁反应是预期的。为了彻底消除循环依赖并遵循依赖注入（DI）原则，我们必须更新所有集成测试，使它们通过 `engine_factory` 或 `engine` fixture 来获取 `Engine` 实例，而不是手动调用 `Engine()`。

我将使用 `write_file` 批量修复受影响的测试文件。

## [WIP] fix(tests): Migrating integration tests to use Engine fixtures

### 错误分析

大量集成测试失败，原因有两个：
1.  **TypeError**: 大多数测试仍在手动调用 `Engine()`，但由于我们修改了构造函数，现在缺少必需的 `strategy` 参数。
2.  **NameError**: 部分测试虽然在代码中尝试调用 `engine_factory`，但其函数签名中未声明请求该 fixture，导致 Pytest 无法注入。

### 用户需求

修复所有因 `Engine` 构造函数变更而失败的集成测试，确保它们正确使用 `engine_factory` 或 `engine` fixture。

### 评论

这次大规模修复是架构重构的“最后一公里”。通过将测试代码迁移到 fixture，我们不仅解决了报错，还利用 `engine_factory` 简化了测试中的组件组装（如 Solver 和 Executor 的默认配置）。这大大提升了测试代码的可维护性。

### 目标

1.  更新 `test_engine_control_flow.py`、`test_engine_core.py` 等 10 个测试文件。
2.  在所有相关的测试函数签名中添加 `engine_factory` 或 `engine` 参数。
3.  将手动的 `Engine(...)` 实例化逻辑替换为对 `engine_factory(...)` 的调用。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-migration #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `test_engine_control_flow.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs
from cascade.runtime import EventBus
from cascade.bus.events import TaskSkipped
from cascade.execution.graph.errors import DependencyMissingError
from cascade.test_utils.helpers import SpySubscriber


@pytest.mark.asyncio
async def test_run_if_true(engine_factory):
    @cs.task
    def condition():
        return True

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    result = await engine.run(flow)
    assert result == "executed"

    # Check no skip events were fired
    assert not spy.events_of_type(TaskSkipped)


@pytest.mark.asyncio
async def test_run_if_false(engine_factory):
    @cs.task
    def condition():
        return False

    @cs.task
    def action():
        return "executed"

    flow = action().run_if(condition())

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(flow)

    # Verify Skip Event using the new helper
    skip_events = spy.events_of_type(TaskSkipped)
    assert len(skip_events) == 1
    assert skip_events[0].task_name == "action"
    assert skip_events[0].reason == "ConditionFalse"


@pytest.mark.asyncio
async def test_cascade_skip(engine_factory):
    @cs.task
    def condition():
        return False

    @cs.task
    def step_a():
        return "A"

    @cs.task
    def step_b(val):
        return f"B got {val}"

    res_a = step_a().run_if(condition())
    res_b = step_b(res_a)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    # Now asserts DependencyMissingError instead of KeyError
    with pytest.raises(DependencyMissingError):
        await engine.run(res_b)

    skip_events = spy.events_of_type(TaskSkipped)

    # Both A and B should be skipped
    skipped_names = sorted([e.task_name for e in skip_events])
    assert skipped_names == ["step_a", "step_b"]

    reason_a = next(e.reason for e in skip_events if e.task_name == "step_a")
    reason_b = next(e.reason for e in skip_events if e.task_name == "step_b")

    assert reason_a == "ConditionFalse"
    assert reason_b == "UpstreamSkipped_Data"
~~~~~

#### Acts 2: 修复 `test_engine_core.py`

此文件需要手动控制 Solver 行为，因此我们使用 `engine_factory` 传入自定义 Solver。

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_core.py
~~~~~
~~~~~python
import pytest

import cascade.sdk as cs
from cascade.execution.graph.model.build import build_graph
from cascade.runtime import EventBus, ExecutionPlan
from cascade.test_utils.helpers import SpyExecutor, MockSolver


# --- Test Case ---


@pytest.mark.asyncio
async def test_engine_follows_solver_plan(engine_factory):
    # 1. Define a simple workflow
    @cs.task
    def task_a():
        pass

    @cs.task
    def task_b(x):
        pass

    workflow = task_b(task_a())
    graph, _, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")

    # 2. Define the execution plan that the MockSolver will return
    mock_plan: ExecutionPlan = [[node_a], [node_b]]

    # 3. Setup test doubles and Engine via factory
    solver = MockSolver(plan=mock_plan)
    executor = SpyExecutor()
    bus = EventBus()

    engine = engine_factory(solver=solver, executor=executor, bus=bus)

    # 4. Run the engine
    await engine.run(workflow)

    # 5. Assert the executor was called in the correct order
    assert len(executor.call_log) == 2
    assert executor.call_log[0].name == "task_a"
    assert executor.call_log[1].name == "task_b"
~~~~~

#### Acts 3: 修复 `test_engine_explicit_control_flow.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_explicit_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs
from cascade.runtime import EventBus


@pytest.mark.asyncio
async def test_explicit_jump_loop(engine):
    @cs.task
    def counter(n: int):
        if n <= 0:
            return cs.Jump(target_key="exit", data=n)
        else:
            return cs.Jump(target_key="continue", data=n - 1)

    loop_node = counter(5)

    jump_selector = cs.select_jump(
        {
            "continue": loop_node,
            "exit": None,
        }
    )

    cs.bind(loop_node, jump_selector)

    # Use the default engine fixture
    final_result = await engine.run(loop_node)

    assert final_result == 0
~~~~~

#### Acts 4: 修复 `test_engine_flow_primitives.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs
from cascade.bus.events import TaskSkipped


@pytest.mark.asyncio
async def test_sequence_executes_in_order(bus_and_spy, engine_factory):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_a():
        execution_order.append("A")

    @cs.task
    def task_b():
        execution_order.append("B")

    @cs.task
    def task_c():
        execution_order.append("C")

    workflow = cs.sequence([task_a(), task_b(), task_c()])

    engine = engine_factory(bus=bus)
    await engine.run(workflow)

    assert execution_order == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_sequence_forwards_last_result(bus_and_spy, engine_factory):
    bus, _ = bus_and_spy

    @cs.task
    def first():
        return "first"

    @cs.task
    def last():
        return "last"

    workflow = cs.sequence([first(), last()])
    engine = engine_factory(bus=bus)
    result = await engine.run(workflow)

    assert result == "last"


@pytest.mark.asyncio
async def test_sequence_aborts_on_failure(bus_and_spy, engine_factory):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_ok():
        execution_order.append("ok")

    @cs.task
    def task_fail():
        execution_order.append("fail")
        raise ValueError("This task fails")

    @cs.task
    def task_never():
        execution_order.append("never")

    workflow = cs.sequence([task_ok(), task_fail(), task_never()])
    engine = engine_factory(bus=bus)

    with pytest.raises(ValueError, match="This task fails"):
        await engine.run(workflow)

    assert execution_order == ["ok", "fail"]


@pytest.mark.asyncio
async def test_sequence_aborts_on_skipped_node(bus_and_spy, engine_factory):
    bus, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(a):
        return "B"

    @cs.task
    def task_c(b):
        return "C"

    false_condition = cs.task(lambda: False)()
    # task_b will be skipped, which should cause task_c to be skipped too.
    workflow = cs.sequence([task_a(), task_b(1).run_if(false_condition), task_c(2)])

    engine = engine_factory(bus=bus)
    await engine.run(workflow)

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 2

    skipped_names = {event.task_name for event in skipped_events}
    assert skipped_names == {"task_b", "task_c"}

    # Verify task_c was skipped because its sequence dependency was skipped
    task_c_skipped_event = next(e for e in skipped_events if e.task_name == "task_c")
    assert task_c_skipped_event.reason == "UpstreamSkipped_Sequence"


@pytest.mark.asyncio
async def test_pipeline_chains_data_correctly(bus_and_spy, engine_factory):
    bus, _ = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    workflow = cs.pipeline(10, [add_one, multiply_by_two])
    engine = engine_factory(bus=bus)
    result = await engine.run(workflow)

    assert result == 22


@pytest.mark.asyncio
async def test_pipeline_with_lazy_initial_input(bus_and_spy, engine_factory):
    bus, _ = bus_and_spy

    @cs.task
    def get_initial():
        return 10

    @cs.task
    def add_one(x):
        return x + 1

    workflow = cs.pipeline(get_initial(), [add_one])
    engine = engine_factory(bus=bus)
    result = await engine.run(workflow)

    assert result == 11


@pytest.mark.asyncio
async def test_pipeline_with_run_if_data_penetration(bus_and_spy, engine_factory):
    bus, spy = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    @cs.task
    def add_three(x):
        return x + 3

    false_condition = cs.task(lambda: False)()
    workflow = cs.pipeline(
        10,
        [
            add_one,
            lambda x: multiply_by_two(x).run_if(false_condition),
            add_three,
        ],
    )

    engine = engine_factory(bus=bus)
    result = await engine.run(workflow)

    # Expected: 10 -> add_one -> 11
    # -> multiply_by_two is skipped
    # -> 11 (from add_one) penetrates to add_three
    # -> 11 + 3 = 14
    assert result == 14

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 1
    assert skipped_events[0].task_name == "multiply_by_two"
~~~~~

#### Acts 5: 修复 `test_engine_inputs.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_inputs.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs


@pytest.mark.asyncio
async def test_engine_executes_param_task(engine):
    # 定义参数
    p = cs.Param("count", type=int)

    # 定义简单的下游任务
    @cs.task
    def double(x):
        return x * 2

    workflow = double(p)

    # 执行，传入 params
    result = await engine.run(workflow, params={"count": 10})

    assert result == 20


@pytest.mark.asyncio
async def test_engine_executes_env_task(monkeypatch, engine):
    monkeypatch.setenv("TEST_VAR", "cascade_value")

    e = cs.Env("TEST_VAR")

    result = await engine.run(e)

    assert result == "cascade_value"
~~~~~

#### Acts 6: 修复 `test_engine_map.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_map.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs


@cs.task
def double(x: int) -> int:
    return x * 2


@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)


@pytest.mark.asyncio
async def test_map_basic(engine):
    inputs = [1, 2, 3]

    # 1. Map 'double' over the inputs -> [2, 4, 6]
    mapped_results = double.map(x=inputs)

    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)

    result = await engine.run(total)
    assert result == 12


@pytest.mark.asyncio
async def test_map_empty(engine):
    inputs = []

    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)

    result = await engine.run(total)
    assert result == 0


@pytest.mark.asyncio
async def test_map_dynamic_input(engine):
    @cs.task
    def generate_numbers(n: int) -> list[int]:
        return list(range(n))

    # 1. Generate [0, 1, 2, 3] dynamically
    nums = generate_numbers(4)

    # 2. Map over the dynamic result -> [0, 2, 4, 6]
    doubled = double.map(x=nums)

    # 3. Sum -> 12
    total = sum_all(numbers=doubled)

    result = await engine.run(total)
    assert result == 12


@pytest.mark.asyncio
async def test_map_multiple_args(engine):
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b

    list_a = [1, 2, 3]
    list_b = [10, 20, 30]

    # Should produce [11, 22, 33]
    mapped = add.map(a=list_a, b=list_b)
    total = sum_all(numbers=mapped)

    result = await engine.run(total)
    assert result == 66


@pytest.mark.asyncio
async def test_map_mismatched_lengths(engine):
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b

    list_a = [1, 2]
    list_b = [10, 20, 30]  # Mismatched

    mapped = add.map(a=list_a, b=list_b)

    with pytest.raises(ValueError, match="mismatched lengths"):
        await engine.run(mapped)
~~~~~

#### Acts 7: 修复 `test_engine_map_policies.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_map_policies.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade.sdk as cs
from cascade.runtime import EventBus
from cascade.bus.events import TaskRetrying
from cascade.test_utils.helpers import SpySubscriber


@pytest.mark.asyncio
async def test_map_with_retry_policy(engine_factory):
    call_counts = {}

    @cs.task
    def flaky_process(x):
        count = call_counts.get(x, 0)
        call_counts[x] = count + 1

        # Fail on first attempt for each item
        if count == 0:
            raise ValueError(f"Fail {x}")
        return x

    inputs = [1, 2, 3]
    mapped = flaky_process.map(x=inputs).with_retry(max_attempts=2, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    results = await engine.run(mapped)

    assert sorted(results) == [1, 2, 3]

    # Check retries occurred
    retries = spy.events_of_type(TaskRetrying)
    assert len(retries) == 3

    # Check call counts
    assert sum(call_counts.values()) == 6
    assert all(c == 2 for c in call_counts.values())


@pytest.mark.asyncio
async def test_map_with_constraints_policy(engine_factory):
    @cs.task
    async def slow_task(x):
        await asyncio.sleep(0.05)
        return time.time()

    # 4 tasks, but system has only 2 slots.
    inputs = [1, 2, 3, 4]
    mapped = slow_task.map(x=inputs).with_constraints(slots=1)

    engine = engine_factory(
        system_resources={"slots": 2},  # Allow 2 concurrent tasks
    )

    start_time = time.time()
    results = await engine.run(mapped)
    duration = time.time() - start_time

    assert len(results) == 4

    # We assert it took clearly longer than a single pass
    assert duration >= 0.09
~~~~~

#### Acts 8: 修复 `test_engine_map_reduce.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_map_reduce.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs


@cs.task
def generate_range(n: int) -> list[int]:
    return list(range(n))


@cs.task
def double(x: int) -> int:
    return x * 2


@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)


@pytest.mark.asyncio
async def test_map_reduce_pipeline(engine):
    # 1. Generate dynamic input: [0, 1, 2, 3, 4]
    nums = generate_range(5)

    # 2. Map: [0, 2, 4, 6, 8]
    doubled_nums = double.map(x=nums)

    # 3. Reduce: 20
    total = sum_all(numbers=doubled_nums)

    result = await engine.run(total)

    assert result == 20
~~~~~

#### Acts 9: 修复 `test_engine_router_pruning.py`

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_engine_router_pruning.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs
from cascade.runtime import EventBus
from cascade.bus.events import TaskSkipped
from cascade.test_utils.helpers import SpySubscriber


@pytest.mark.asyncio
async def test_pruning_exclusive_branches(engine_factory):
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def branch_a():
        return "A"

    @cs.task
    def branch_b(val):
        return "B"  # Should be pruned

    @cs.task
    def dummy_dep():
        return "DEP"

    @cs.task
    def branch_b_upstream(dep):
        return "B_UP"  # Should also be pruned (recursive)

    b_chain = branch_b(branch_b_upstream(dummy_dep()))

    router = cs.Router(selector=get_route(), routes={"a": branch_a(), "b": b_chain})

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    result = await engine.run(workflow)
    assert result == "A"

    # Check pruning events
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}

    assert "branch_b" in skipped_names
    assert "branch_b_upstream" in skipped_names

    # Verify reasons
    for e in skipped:
        assert e.reason == "Pruned"


@pytest.mark.asyncio
async def test_pruning_shared_dependency(engine_factory):
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def shared_task():
        return "SHARED"

    @cs.task
    def branch_a(dep):
        return f"A({dep})"

    @cs.task
    def branch_b(dep):
        return f"B({dep})"  # Should be pruned, but 'dep' should not

    # shared_task is used by BOTH branches
    shared = shared_task()

    router = cs.Router(
        selector=get_route(), routes={"a": branch_a(shared), "b": branch_b(shared)}
    )

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(bus=bus)

    result = await engine.run(workflow)
    assert result == "A(SHARED)"

    # Check pruning
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}

    assert "branch_b" in skipped_names
    assert "shared_task" not in skipped_names  # MUST NOT be pruned

    # Only branch_b should be pruned
    assert len(skipped) == 1
~~~~~

#### Acts 10: 修复 `test_static_integrity.py`

~~~~~act
write_file
packages/cascade-runtime/tests/legacy_graph/integration/test_static_integrity.py
~~~~~
~~~~~python
import pytest
import cascade.sdk as cs
from cascade.execution.graph.model.exceptions import StaticGraphError


@pytest.mark.asyncio
async def test_task_returning_lazy_result_is_forbidden_at_runtime(engine):
    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        return task_b()

    workflow = task_a_violating()

    # Use default engine fixture
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' illegally returned a LazyResult",
    ):
        await engine.run(workflow)
~~~~~

### 下一步建议

我已修复了所有受影响的集成测试。现在请再次运行 `pytest`。由于 `test_engine_constraints.py` 之前也报错了且未包含在本次 `write_file` 中，如果它依然失败，请提供该文件的内容，我将对其进行同样的修复。
