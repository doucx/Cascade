您提供的反馈非常清晰，测试失败的日志直接指出了问题所在。我们正在一个正确的轨道上：通过测试驱动的方式，逐步发现并修复实现中的边缘情况。

我将生成一个计划来修复这个失败的测试。

## [WIP] fix(test): 修复 `pause_and_resume` 测试中的竞争条件

### 错误分析
`test_polling_pause_and_resume_e2e` 的失败日志 `AssertionError: assert 'task_b' not in {'task_a', 'task_b'}` 表明，当我们断言 `task_b` 不应该开始执行时，它实际上已经开始了。

这是典型的**测试逻辑中的竞争条件（race condition）**，而非 `SqliteConnector` 本身的错误。问题在于：

1.  **测试流程**: 测试代码等待 `task_a` 完成，然后才发布对 `task_b` 的暂停命令。
2.  **Engine 行为**: `Engine` 的执行速度非常快。在 `task_a` 完成后，`Engine` 几乎立即就会调度 `task_b`，因为它此时还没有收到暂停命令。
3.  **时序冲突**: 当测试代码发布暂停命令时，`Engine` 很可能已经将 `task_b` 放入了执行队列。`Connector` 的轮询任务在稍后（最多 `POLL_INTERVAL` 秒后）才将这个暂停命令通知给 `Engine`，但为时已晚。

我的上一个修复方案解决了 connector 的启动竞争问题，但这个测试用例本身的逻辑缺陷导致了新的失败。

### 用户需求
修复 `test_polling_pause_and_resume_e2e` 测试用例，消除其中的竞争条件，使其能够可靠地验证 `SqliteConnector` 的暂停和恢复功能。

### 评论
这个问题的标准解决方案是重构测试，确保我们在 `Engine` 无法立即调度下游任务的时间窗口内发布控制命令。`test_e2e_control_plane.py` 中的测试已经为我们提供了完美的模式：

1.  让上游任务（`task_a`）变得很慢。
2.  使用 `asyncio.Event` 来精确地等待 `task_a` **开始**执行。
3.  在 `task_a` 正在长时间运行时，发布对 `task_b` 的暂停命令。
4.  这样，当 `task_a` 最终完成时，`Engine` 的 `Connector` 轮询任务已经有足够的时间从数据库中读取并应用了暂停约束。

这种方法消除了竞争，能够确定性地测试 `Engine` 在决策是否执行 `task_b` 之前是否正确地处理了外部控制信号。

### 目标
1.  修改 `tests/engine/e2e/test_e2e_sqlite_connector.py` 文件。
2.  重构 `test_polling_pause_and_resume_e2e` 测试用例的实现。
3.  引入一个 `slow_task_a`，它会长时间运行以创造一个发布约束的时间窗口。
4.  使用 `asyncio.Event` 来同步测试主流程和 `slow_task_a` 的启动。
5.  调整断言逻辑以匹配新的任务名称。

### 基本原理
本计划将使用一个 `patch_file` 操作来精确地替换 `test_e2e_sqlite_connector.py` 中有问题的测试用例函数。`old_str` 将是旧的、存在竞争条件的实现，而 `new_str` 将是遵循了健壮测试模式的新实现。这是一种原子化且风险最低的修复方法，因为它只修改了测试逻辑，而没有触及已经通过其他测试的 `SqliteConnector` 实现。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/tooling #scope/dx #ai/refine #task/domain/testing #task/object/e2e-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_polling_pause_and_resume_e2e` 的竞争条件

我们将用一个更健壮的、无竞争条件的版本来替换现有的测试用例实现。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_polling_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies the core polling loop for pause and resume functionality.
    """
    _, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(task_a())

    async with controller_connector:
        # Start the engine in the background
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # Wait for task_a to finish
        await asyncio.sleep(POLL_INTERVAL + 0.1) 

        # Publish a pause for task_b
        scope = "task:task_b"
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        pause_payload = {
            "id": "pause-b", "scope": scope, "type": "pause", "params": {}
        }
        await controller_connector.publish(topic, pause_payload)

        # Wait for the poll interval to pass
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # Assert that task_b has NOT started
        started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
        assert "task_b" not in started_tasks

        # Now, publish a resume command
        await controller_connector.publish(topic, {})

        # Wait for the poll interval again
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # The workflow should now complete
        final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
        assert final_result == "B"

    finished_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionFinished) if e.status == "Succeeded"}
    assert finished_tasks == {"task_a", "task_b"}
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_polling_pause_and_resume_e2e(engine, controller_connector, bus_and_spy):
    """
    Verifies the core polling loop for pause and resume functionality.
    This version fixes a race condition in the test logic.
    """
    _, spy = bus_and_spy
    task_a_started = asyncio.Event()

    @cs.task
    async def slow_task_a():
        task_a_started.set()
        # Sleep long enough for the test to publish a constraint and for a poll cycle to run
        await asyncio.sleep(POLL_INTERVAL * 2)
        return "A"

    @cs.task
    def task_b(dep):
        return "B"

    workflow = task_b(slow_task_a())

    async with controller_connector:
        # Start the engine in the background
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # 1. Wait for the slow task to start executing
        await asyncio.wait_for(task_a_started.wait(), timeout=1.0)

        # 2. While task_a is running, publish a pause for task_b
        scope = "task:task_b"
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        pause_payload = {
            "id": "pause-b", "scope": scope, "type": "pause", "params": {}
        }
        await controller_connector.publish(topic, pause_payload)

        # 3. Wait for slow_task_a to finish. During this time, the polling
        #    task in the engine MUST have run and picked up the pause constraint.
        #    We let slow_task_a finish its sleep.
        await asyncio.sleep(POLL_INTERVAL * 2 + 0.1)
        
        # 4. Assert that task_b has NOT started
        started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
        assert "task_b" not in started_tasks, "task_b started despite pause constraint"

        # 5. Now, publish a resume command
        await controller_connector.publish(topic, {})

        # 6. Wait for the next poll interval for the resume to be picked up
        await asyncio.sleep(POLL_INTERVAL + 0.1)

        # 7. The workflow should now complete
        final_result = await asyncio.wait_for(engine_run_task, timeout=1.0)
        assert final_result == "B"

    finished_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionFinished) if e.status == "Succeeded"}
    assert finished_tasks == {"slow_task_a", "task_b"}
~~~~~

### 下一步建议
我们已经修复了测试逻辑中的竞争条件。现在，测试套件应该能够准确地反映 `SqliteConnector` 的行为。

请再次运行测试。如果所有测试都通过，我们将正式完成路线图的**第一步**，并可以充满信心地进入**第二步：[性能优化] 增强 Unix Domain Socket (UDS) 信号机制**。
