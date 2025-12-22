好的，测试已通过，我们正式进入路线图的步骤 4：为 UDS 信号机制编写专门的端到端测试。

按照你的要求，我将创建一个 `[WIP]` 计划。这非常明智，因为编写与特定时序相关的测试有时需要微调。

这个新测试的核心是验证 UDS 机制**真的**实现了其核心承诺：近乎瞬时的唤醒，而不是仅仅功能正确。

## [WIP] test(connector): Add E2E test for SqliteConnector UDS signaling

### 用户需求
为 `SqliteConnector` 的 Unix Domain Socket (UDS) 信号功能添加一个专门的端到端测试，以验证其低延迟的唤醒能力。

### 评论
这是确保新功能质量的关键一步。此前的测试验证了系统的最终一致性（在某个时间点后状态是对的），而这个新测试将验证其**性能**——即状态更新的速度是否符合预期。明确地断言响应时间快于轮询间隔，是对 UDS 机制有效性的最终证明。

### 目标
1.  在 `tests/engine/e2e/test_e2e_sqlite_connector.py` 文件中添加一个新的测试函数 `test_uds_signaling_is_near_instant`。
2.  使用 `@pytest.mark.skipif` 装饰器，确保此测试仅在非 Windows 平台上运行。
3.  测试逻辑将：
    a. 启动一个 `Engine` 实例并运行一个简单的任务。
    b. 立即通过 `controller_connector` 发布一个全局 `pause` 约束，确保工作流在启动后被阻塞。
    c. 在短暂延迟后，发布一个 `resume` 命令，并精确测量从发布命令到工作流完成所需的时间。
    d. **断言**所测量的时长远小于 `POLL_INTERVAL`，从而证明 `Engine` 是被 UDS 信号唤醒的，而不是等待下一个轮询周期。

### 基本原理
我们将向现有的测试文件中追加一个新的测试用例。通过 `patch_file` 操作，我们可以精确地将新测试函数添加到文件末尾。测试的核心在于时间测量：如果 `Engine` 能够在几十毫秒内完成，而轮询间隔是 200 毫秒，那么唯一的解释就是 UDS 信号起了作用。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/storage #task/object/sqlite-connector #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 向测试套件中添加 UDS 信号验证测试

我将使用 `patch_file` 将新的测试用例添加到 `test_e2e_sqlite_connector.py` 的末尾。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
        # The engine's internal cleanup should resume execution.
        final_result = await asyncio.wait_for(
            engine_run_task, timeout=POLL_INTERVAL * 2
        )
        assert final_result == "done"
~~~~~
~~~~~python
        # The engine's internal cleanup should resume execution.
        final_result = await asyncio.wait_for(
            engine_run_task, timeout=POLL_INTERVAL * 2
        )
        assert final_result == "done"


@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not available on Windows")
@pytest.mark.asyncio
async def test_uds_signaling_is_near_instant(engine, controller_connector, bus_and_spy):
    """
    Verifies that UDS signaling wakes up the engine almost instantly,
    much faster than the polling interval.
    """
    scope = "global"
    topic = "cascade/constraints/global"

    @cs.task
    def my_task():
        return "done"

    workflow = my_task()

    async with controller_connector:
        # 1. Pause the engine immediately upon start
        pause_payload = {"id": "pause-uds", "scope": scope, "type": "pause", "params": {}}
        await controller_connector.publish(topic, pause_payload)

        # 2. Start the engine. It should connect, subscribe, get the pause, and block.
        engine_run_task = asyncio.create_task(engine.run(workflow))

        # Give the engine a moment to initialize and enter the blocked state
        await asyncio.sleep(POLL_INTERVAL / 2)
        assert not engine_run_task.done(), "Engine finished prematurely despite pause"

        # 3. Resume and measure the wakeup time
        start_time = time.time()
        await controller_connector.publish(topic, {})  # Resume command
        await asyncio.wait_for(engine_run_task, timeout=POLL_INTERVAL * 2)
        duration = time.time() - start_time

    # 4. Assert that the wakeup was much faster than polling
    assert duration < POLL_INTERVAL, (
        f"Wakeup took {duration:.4f}s, which is not faster than the polling "
        f"interval of {POLL_INTERVAL}s. UDS signal likely failed."
    )
~~~~~

### 下一步建议
请运行测试。
-   **如果通过**：这标志着我们已经成功实现了 `SqliteConnector` 的 UDS 增强，并用测试保证了其质量。我们可以准备一个 `[COMMIT]` 计划来正式合并这个功能。
-   **如果失败**：我们可以分析失败原因。由于我们已经验证了核心逻辑，失败很可能与测试中的时序假设有关，我们可以进行微调。
