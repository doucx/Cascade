好的，我们立即开始编写集成测试。

我将生成一个 `[WIP]` 计划，用于在 `tests/py/runtime/test_engine_constraints.py` 中添加一个全面的测试用例。这个测试将严格遵循我们已建立的“通过事件流验证意图”的原则，确保新实现的暂停与恢复功能在任务级别上是正确且健壮的。

## [WIP] test(runtime): 为任务级暂停与恢复功能添加集成测试

### 用户需求
为里程碑 3.1 实现的“任务级暂停与恢复”功能编写一个集成测试。该测试需要验证整个控制回路：
1.  施加一个针对特定任务的 `pause` 约束。
2.  确认该任务被正确挂起，而其他任务不受影响。
3.  发送一个 `resume` 命令。
4.  确认被挂起的任务恢复执行，并且整个工作流最终成功完成。

### 评论
这是确保我们新功能质量的关键步骤。一个可靠的集成测试不仅能验证当前实现的正确性，还能在未来的重构中充当安全网，防止回归问题的发生。通过模拟 MQTT 消息并断言 `Engine` 发出的事件，我们可以创建一个与 UI 无关的、高度可靠的测试用例。

### 目标
1.  在 `tests/py/runtime/test_engine_constraints.py` 文件中，新增一个名为 `test_engine_pauses_and_resumes_specific_task` 的测试用例。
2.  该测试将使用 `MockConnector` 模拟来自 `cs-controller` 的 `pause` 和 `resume` MQTT 消息。
3.  使用 `SpySubscriber` 捕获 `Engine` 在整个执行过程中的所有事件。
4.  通过断言事件的顺序和内容（例如，`TaskExecutionFinished` for `task_a`, an absence of events for `task_b`, followed by `TaskExecutionFinished` for `task_b` and `task_c` after resume），来验证控制逻辑的正确性。

### 基本原理
测试将创建一个 A -> B -> C 的三步工作流。在任务 A 完成后，测试会注入一个针对 `task:task_b` 的暂停约束。此时，我们断言 `task_b` 不会启动。然后，我们注入一个恢复命令，并断言 `task_b` 和 `task_c` 依次恢复执行并成功完成。所有对系统状态的判断都将基于 `SpySubscriber` 捕获的事件流，这是一种健壮且解耦的测试策略。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/runtime #comp/tests
#concept/executor #scope/core
#ai/instruct
#task/domain/control #task/object/constraint-system #task/action/refinement #task/state/continue

---
### Script

#### Acts 1: 在 `test_engine_constraints.py` 中添加新的集成测试

我们将通过 `patch_file` 向测试文件中追加新的测试用例。

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
        executor=MockExecutor(),
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

    # 3. Wait for 'task_a' to finish. This ensures the engine is ready for 'task_b'.
    await wait_for_task_finish(spy, "task_a")

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

    # 5. Wait briefly and assert that 'task_b' has NOT started
    await asyncio.sleep(0.2)
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "'task_b' started despite pause constraint"

    # 6. Inject a RESUME command for 'task_b'
    # An empty payload on a retained topic clears the constraint.
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", ""
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
    assert final_result == "C after B after A"
~~~~~

### 下一步建议
我们已经完成了里程碑 3.1 的核心功能开发和测试。根据路线图，下一步是进入**里程碑 3.2: 并发管理 (Concurrency Management)**。

这项工作将允许我们通过外部指令来限制特定任务的并发执行数量，例如 `cs-controller set-limit --scope "task:api_call" --concurrency 5`。这将进一步增强 Cascade 保护下游系统、防止过载的能力。

如果你同意，我将开始分析并生成实现此功能的计划。
