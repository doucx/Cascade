好的，我们现在开始执行重构路线图的第二步。

根据计划，我们的目标是编写一个专门的、当前预期会失败的测试用例。这个测试将精确地复现 `Engine` 在启动时未能正确响应预先存在的 `pause` 约束的竞态条件。拥有一个稳定失败的测试是测试驱动开发（TDD）中的“红灯”阶段，为我们下一步的修复工作提供了明确的目标。

我将生成一个计划，在 `tests/py/e2e/test_e2e_control_plane.py` 文件中添加这个新的测试用例 `test_startup_pause_is_respected`。

## [WIP] test: 为启动竞态条件添加失败的测试

### 用户需求
遵循重构路线图的第二步，需要创建一个新的端到端测试，该测试应能可靠地证明 `Engine` 在启动时存在竞态条件，即未能遵守在它启动前就已存在的 `pause` 约束。

### 评论
这是关键的“红灯”步骤。通过创建一个稳定、可重现的失败测试，我们为后续的修复工作（“绿灯”步骤）建立了一个明确、可验证的目标。这个测试将成为防止未来发生类似回归问题的安全网。

### 目标
1.  在 `tests/py/e2e/test_e2e_control_plane.py` 文件中添加一个新的测试函数 `test_startup_pause_is_respected`。
2.  该测试将首先发布一个全局 `pause` 约束，然后启动 `Engine`。
3.  断言在 `Engine` 启动后，没有任何任务被执行，从而证明 `pause` 约束被忽略了（测试失败）。

### 基本原理
我们利用在步骤一种确定性的 `InProcessConnector`。由于 `subscribe` 方法现在可以同步地传递所有保留消息，我们可以确保 `Engine` 在其 `run` 方法开始执行调度循环之前，就已经有机会收到 `pause` 约束。

当前的 `Engine` 实现存在缺陷，它不会等待这个同步过程完成，而是立即开始调度任务，从而导致竞态条件。这个测试就是为了暴露这一缺陷。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/concurrency #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 添加 `test_startup_pause_is_respected` 测试用例

我们将新的测试函数添加到 `test_e2e_control_plane.py` 文件中。

~~~~~act
patch_file
tests/py/e2e/test_e2e_control_plane.py
~~~~~
~~~~~python
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

    # 4. ASSERT: The engine is paused.
    # Yield control to allow engine to initialize and process the retained pause message.
    # With deterministic connector, this should be instant.
    await asyncio.sleep(0)
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 0, (
        "Task started execution despite global pause constraint"
    )

    # 5. ACT: Controller issues a RESUME command.
    await controller.resume(scope="global")

    # 6. ASSERT: The engine unpauses and completes the workflow.
    # The run task should now complete without timing out.
    final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
    assert final_result == "done"

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 1
    assert started_events[0].task_name == "my_task"
~~~~~
~~~~~python
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

    # 4. ASSERT: The engine is paused.
    # Yield control to allow engine to initialize and process the retained pause message.
    # With deterministic connector, this should be instant.
    await asyncio.sleep(0)
    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 0, (
        "Task started execution despite global pause constraint"
    )

    # 5. ACT: Controller issues a RESUME command.
    await controller.resume(scope="global")

    # 6. ASSERT: The engine unpauses and completes the workflow.
    # The run task should now complete without timing out.
    final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
    assert final_result == "done"

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 1
    assert started_events[0].task_name == "my_task"


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

    # ASSERT: After giving the engine a moment to process initial messages,
    # no tasks should have started.
    await asyncio.sleep(0.01)  # A small sleep to let the loop run and fail

    started_events = spy.events_of_type(TaskExecutionStarted)
    assert len(started_events) == 0, (
        "Task started execution despite global pause constraint"
    )

    # Cleanup the background task to avoid warnings
    engine_run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_run_task
~~~~~

### 下一步建议
我们已经成功地为 Bug 编写了一个将会失败的回归测试。现在，测试套件处于“红灯”状态。

下一步是执行路线图中的 **步骤 3: [绿灯] 修复引擎的启动逻辑**，让这个新测试和所有其他测试都通过。如果你同意，我将开始分析并生成修复该问题的计划。
