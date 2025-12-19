遵照 **重构路线图：实现 Cascade 的并发安全** 中的指示，我们将执行 **步骤 4**。

我们将编写一个新的测试用例 `test_runtime_pause_interrupts_stage`，旨在揭示 `Engine` 在任务执行中途无法及时响应外部 `pause` 约束的并发缺陷。这个测试预期会**失败**（红灯），从而证明我们需要在下一阶段引入双重检查锁定 (Double-Check Locking) 机制。

这是一个 `[WIP]` 计划，仅涉及文件修改。

## [WIP] test: 添加运行时暂停的回归测试

### 用户需求
在 `tests/py/e2e/test_e2e_control_plane.py` 中添加一个新的集成测试 `test_runtime_pause_interrupts_stage`。该测试将模拟在一个长任务运行期间发出 `pause` 指令，并验证系统是否能够正确阻止后续依赖任务的启动。

### 评论
这个测试是并发安全重构路线图的关键一步。它通过构造一个确定的竞态条件场景（Slow Task A running -> Pause issued -> Task A finishes -> Task B scheduled），来验证 `Engine` 调度循环是否能够在任务间隙正确处理IO消息并更新权限状态。当前的 `Engine` 实现很可能会因为处理 IO 消息的协程优先级问题或缺乏同步点而无法通过此测试。

### 目标
1.  在 `test_e2e_control_plane.py` 中追加 `test_runtime_pause_interrupts_stage` 测试函数。
2.  确保测试使用确定性的 `InProcessConnector` 和同步原语 (`asyncio.Event`)，避免不稳定的 `sleep` 依赖（除了用于模拟任务本身耗时的部分）。
3.  复现目标 Bug：`Task B started despite global pause!`。

### 基本原理
我们遵循 TDD (测试驱动开发) 的 "Red-Green-Refactor" 循环。在修复并发 Bug 之前，必须先有一个能稳定复现该 Bug 的测试。这确保了我们不仅修复了问题，而且防止了未来的回归。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/engine-control #task/action/test-runtime-pause #task/state/continue

---

### Script

#### Acts 1: 添加测试用例

我们将使用 `patch_file` 在 `tests/py/e2e/test_e2e_control_plane.py` 的末尾追加新的测试函数。

~~~~~act
patch_file
tests/py/e2e/test_e2e_control_plane.py
~~~~~
~~~~~python
    engine_run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_run_task
~~~~~
~~~~~python
    engine_run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await engine_run_task


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

    # Wait for A to start
    await asyncio.wait_for(task_a_started.wait(), timeout=1.0)

    # Issue PAUSE immediately
    await controller.pause(scope="global")

    # Wait long enough for A to finish and for Engine to potentially schedule B
    await asyncio.sleep(0.7)

    # 3. ASSERT
    # Task B should NOT have started
    b_events = [
        e for e in spy.events_of_type(TaskExecutionStarted)
        if e.task_name == "task_b"
    ]
    assert len(b_events) == 0, "Task B started despite global pause!"

    # Cleanup
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass
~~~~~

### 下一步建议
一旦这个计划被执行并且（预期中）测试失败，我们将继续执行路线图的 **步骤 5: [绿灯] 实现双重检查锁定 (Double-Check Lock)**，修改 `Engine` 代码以通过此测试。
