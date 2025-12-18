## [WIP] fix: 修复集成测试中的时序竞争条件

### 错误分析
测试失败 `AssertionError: task_b should have been paused` 是由于测试代码与 `Engine` 执行循环之间的竞争条件（Race Condition）导致的。

当前的测试逻辑是：
1.  等待任务 A **完成** (`TaskExecutionFinished`)。
2.  注入暂停指令。

然而，在 `Engine` 内部，当任务 A 完成时，控制流会立即进入下一个迭代（Stage 2），并在极短的时间内完成对任务 B 的约束检查并提交执行。测试代码在收到 A 完成的事件后，还没来得及注入暂停指令，`Engine` 就已经把 B 启动了。

### 用户需求
修复测试中的竞争条件，确保暂停指令在任务 B 启动前生效。

### 评论
在测试异步系统时，时序控制至关重要。为了拦截两个连续阶段之间的执行，我们需要在“前一个阶段正在运行”时就注入控制指令，而不是等到它结束。这是验证流式系统行为的标准模式。

### 目标
1.  在测试文件中添加 `wait_for_task_start` 辅助函数。
2.  修改 `test_engine_pauses_on_global_pause_constraint` 测试逻辑：
    *   改为等待任务 A **开始** (`TaskExecutionStarted`)。
    *   在任务 A 运行时注入暂停指令。
    *   （可选）为了确保 A 不会瞬间完成，可以在 A 中添加微小的 sleep，或者仅仅依靠 `Connector` 的 await 切换上下文通常就足够了。鉴于 `MockExecutor` 几乎是瞬时的，我们将依赖事件循环的调度顺序：只要在 A 开始后、A 结束前注入，或者在 A 结束后、B 检查前注入。
    *   最稳妥的策略：**在 A 开始后立即注入**。因为 MockExecutor 虽然快，但也是异步的 (`async def execute`)，且 `Engine` 在 gather 等待。只要我们在 A 运行期间更新了 `ConstraintManager`，当 `Engine` 醒来处理 Stage 2 时，它就会看到更新后的约束。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #concept/concurrency
#ai/instruct
#task/domain/testing #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正测试时序

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~
