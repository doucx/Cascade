我们面临的挑战是典型的重构“长尾效应”：当我们修改了底层核心类（`Engine`）的构造函数契约时，所有直接实例化它的测试代码都必须同步更新。

为了高效且稳健地解决这个问题，我将利用我们在 `conftest.py` 中新创建的 `engine_factory` fixture。这个工厂已经封装了默认的策略构建逻辑（包括对 `CASCADE_BACKEND` 的支持），可以作为之前硬编码在 `Engine` 内部逻辑的完美替代品。

我将分批次修复受影响的测试文件。第一步，我们将重点修复 `cascade-runtime` 中的核心集成测试，特别是处理那些导致 `patch_file` 匹配冲突的复杂文件。

## [WIP] fix(tests): Migrate integration tests to use engine_factory

### 错误分析
由于 `Engine.__init__` 现在强制要求 `strategy` 参数，现有的测试代码在调用 `Engine(...)` 或 `cs.Engine(...)` 时因为缺少该参数而失败。之前尝试修复 `test_engine_constraints.py` 时由于代码块过于相似导致 `patch_file` 匹配歧义。

### 用户需求
修复 `cascade-runtime` 及其相关包中的所有集成测试，使其符合 `Engine` 的新构造函数契约，同时保留测试对特定组件（如 `MockConnector`, `TimedMockExecutor`）的自定义能力。

### 评论
使用 `engine_factory` 是最优雅的方案。它允许测试通过关键字参数按需覆盖组件，而无需关心 `strategy` 的繁琐组装过程。对于那些只需要标准引擎的测试，直接使用 `engine` fixture 即可。我们将通过增加 `patch_file` 的上下文行（锚点）来解决匹配冲突问题。

### 目标
1.  修复 `cascade-runtime/tests/integration/` 目录下的核心集成测试。
2.  将手动实例化 `Engine` 的逻辑替换为调用 `engine_factory`。
3.  确保 `MockConnector` 和 `TimedMockExecutor` 被正确注入。

### 基本原理
`engine_factory` fixture 接受 `solver`, `executor`, `bus` 和其他 `Engine` 参数。它会自动处理 `strategy` 的构建逻辑（除非被显式覆盖）。在测试中，我们将：
-   将 `engine_factory` 加入测试函数或 fixture 的参数列表。
-   将 `Engine(solver=..., executor=..., ...)` 替换为 `engine_factory(solver=..., executor=..., ...)`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_engine_constraints.py` 中的匹配冲突

我们将通过增加上下文行来精确替换 `test_engine_constraints.py` 中的三处 `Engine` 实例化。

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=EventBus(),
        connector=mock_connector,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine_with_connector(engine_factory, mock_connector):
    return engine_factory(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=EventBus(),
        connector=mock_connector,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_engine_pauses_on_global_pause_constraint(mock_connector, bus_and_spy):
    from cascade.spec.dsl.task import task
    from cascade.bus.events import TaskExecutionStarted

    bus, spy = bus_and_spy
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_engine_pauses_on_global_pause_constraint(engine_factory, mock_connector, bus_and_spy):
    from cascade.spec.dsl.task import task
    from cascade.bus.events import TaskExecutionStarted

    bus, spy = bus_and_spy
    engine = engine_factory(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_engine_pauses_and_resumes_specific_task(mock_connector, bus_and_spy):
    from cascade.spec.dsl.task import task
    from cascade.bus.events import (
        TaskExecutionStarted,
        TaskExecutionFinished,
    )

    bus, spy = bus_and_spy
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_engine_pauses_and_resumes_specific_task(engine_factory, mock_connector, bus_and_spy):
    from cascade.spec.dsl.task import task
    from cascade.bus.events import (
        TaskExecutionStarted,
        TaskExecutionFinished,
    )

    bus, spy = bus_and_spy
    engine = engine_factory(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=bus,
        connector=mock_connector,
    )
~~~~~

#### Acts 2: 修复 `test_engine_concurrency.py`

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=EventBus(),
        connector=mock_connector,
        system_resources={},
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(engine_factory, mock_connector):
    return engine_factory(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=EventBus(),
        connector=mock_connector,
        system_resources={},
    )
~~~~~

#### Acts 3: 修复 `test_engine_flow_primitives.py`

这个文件中有大量重复的 `Engine` 调用。我们将把它们统一替换为使用 `engine_factory`。

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
    workflow = cs.sequence([task_a(), task_b(), task_c()])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)
~~~~~
~~~~~python.new
    workflow = cs.sequence([task_a(), task_b(), task_c()])

    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
    workflow = cs.sequence([first(), last()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
    workflow = cs.sequence([first(), last()])
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
    workflow = cs.sequence([task_ok(), task_fail(), task_never()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="This task fails"):
~~~~~
~~~~~python.new
    workflow = cs.sequence([task_ok(), task_fail(), task_never()])
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="This task fails"):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
    # task_b will be skipped, which should cause task_c to be skipped too.
    workflow = cs.sequence([task_a(), task_b(1).run_if(false_condition), task_c(2)])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)
~~~~~
~~~~~python.new
    # task_b will be skipped, which should cause task_c to be skipped too.
    workflow = cs.sequence([task_a(), task_b(1).run_if(false_condition), task_c(2)])

    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
    def add_one(x):
        return x + 1

    workflow = cs.pipeline(get_initial(), [add_one])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
    def add_one(x):
        return x + 1

    workflow = cs.pipeline(get_initial(), [add_one])
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~python.old
        ],
    )

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
        ],
    )

    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)
~~~~~

注意：我还必须在受影响的测试函数签名中添加 `engine_factory` 参数。

#### Acts 4: 修复 `test_engine_retry.py`

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_retry.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_retry_success_after_failure():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_retry_success_after_failure(engine_factory):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_retry.py
~~~~~
~~~~~python.old
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(task_with_retry)
~~~~~
~~~~~python.new
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(task_with_retry)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_retry.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_retry_exhausted_failure():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_retry_exhausted_failure(engine_factory):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_retry.py
~~~~~
~~~~~python.old
    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="Always fail"):
~~~~~
~~~~~python.new
    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="Always fail"):
~~~~~

#### Acts 5: 修复 `test_engine_control_flow.py`

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_run_if_true():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_run_if_true(engine_factory):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(flow)
~~~~~
~~~~~python.new
    bus = EventBus()
    spy = SpySubscriber(bus)
    engine = engine_factory(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(flow)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_run_if_false():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_run_if_false(engine_factory):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_cascade_skip():
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_cascade_skip(engine_factory):
~~~~~

### 下一步建议
我们已经完成了 `cascade-runtime` 核心集成测试的第一波修复。下一步我将修复 `cascade-library` 中的测试，那里的测试大多通过 `cs.Engine` 调用。我也将使用相同的 `engine_factory` 模式来确保它们的一致性。修复完成后，我们将尝试运行完整的测试套件。
