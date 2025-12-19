这是 **步骤 5: [绿灯]** 的执行。

我们分析发现，之前的测试失败 `AssertionError` 是由于测试代码本身给定的初始等待时间（0.2秒）过短，导致在引擎启动和调度第一个任务之前断言就执行了。

此外，经过对 `Engine` 代码的审查，我们发现防止死锁的关键代码 `self._wakeup_event.set()` **已经存在**于 `_on_constraint_update` 方法中（可能是在之前的步骤中引入的）。因此，本次“修复”的核心是修正测试用例的缺陷，以验证现有代码的正确性。如果测试修正后通过，则证明系统实际上是健康的。

## [WIP] fix(test): 修正速率限制测试的时序问题

### 用户需求
修正 `test_updating_rate_limit_unblocks_engine` 测试用例，将初始阶段的等待时间从 0.2 秒增加到 2.0 秒，以确保 `Engine` 有足够的时间启动并处理第一个任务。

### 评论
测试的准确性至关重要。当前的测试失败是一个“假阳性”——它报告了错误，但不是因为被测系统有问题，而是因为测试本身太急躁。通过放宽时间限制，我们将能够看到系统的真实行为：它是否能在更新约束后解除阻塞。

### 目标
1.  修改 `tests/py/e2e/test_e2e_runtime_control_updates.py`。
2.  将等待循环从 `range(2)` 增加到 `range(20)`。

### 基本原理
在异步测试中，特别是涉及 `InProcessConnector` 和 `MockWorkExecutor` 的集成测试，必须预留足够的缓冲时间来容纳事件循环的调度开销。0.2 秒对于完整的“启动->连接->订阅->调度->执行”链路来说过于紧张。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/engine-control #task/action/fix-test-timing #task/state/continue

---

### Script

#### Acts 1: 增加测试等待时间

~~~~~act
patch_file
tests/py/e2e/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python
    # Wait for the first task to finish, confirming the engine is running and throttled
    for _ in range(2): # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break
~~~~~
~~~~~python
    # Wait for the first task to finish, confirming the engine is running and throttled
    for _ in range(20): # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break
~~~~~

### 下一步建议
运行修正后的测试。如果通过，说明 `Engine` 的并发控制逻辑是正确的。如果仍然失败（这次应该是超时），则说明确实存在深层死锁问题，我们需要进一步排查。
