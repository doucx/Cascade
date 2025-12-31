## [WIP] test: 创建生命周期测试以暴露 VMStrategy 的死锁问题

### 用户需求
创建一个新的集成测试，使用最简单的单节点工作流来测试 `VMExecutionStrategy`。该测试旨在暴露并驱动修复当前策略层存在的死锁问题。

### 评论
当前的 TCO 测试因 `VMExecutionStrategy` 中 `await reactor.run()` 导致的死锁而挂起。这个新测试通过将问题简化到最基本的形式——执行单个任务——来隔离生命周期管理缺陷。它将迫使我们重构策略，从错误的“同步等待”模式转变为正确的“后台运行与事件订阅”模式。

### 目标
1.  创建新的测试文件 `packages/cascade-engine/tests/integration/test_vm_strategy_lifecycle.py`。
2.  在该文件中，编写一个测试用例，使用 `VMExecutionStrategy` 运行一个无依赖的简单任务。
3.  这个测试在当前代码下会因为超时而失败，从而建立一个清晰的 RED 状态。

### 基本原理
根据 TDD 原则，我们必须先有一个能稳定复现问题的最小化失败测试。这个测试将作为我们重构 `VMExecutionStrategy` 的“安全网”和“驱动力”。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/engine #concept/executor #scope/dx #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建新的生命周期测试文件

我们将创建一个新的测试文件，专门用于验证 `VMExecutionStrategy` 的核心生命周期。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_strategy_lifecycle.py
~~~~~
~~~~~python
import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_vm_strategy_completes_single_node_workflow_and_returns():
    """
    This is the most basic test for VMExecutionStrategy.
    It verifies that the strategy can:
    1. Start the Reactor.
    2. Execute a single task.
    3. Detect completion.
    4. Stop the Reactor.
    5. Return the final result.

    Under the current flawed implementation, this test will hang indefinitely.
    """
    @cs.task
    def simple_task():
        return "SUCCESS"

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We run this with a timeout to prevent the test suite from hanging forever.
    # The test will fail by raising TimeoutError, which is our expected RED state.
    try:
        result = await asyncio.wait_for(
            engine.run(workflow, use_vm=True),
            timeout=2.0
        )
        assert result == "SUCCESS"
    except asyncio.TimeoutError:
        pytest.fail("The VMExecutionStrategy hung and did not complete within the timeout.")
~~~~~

### 下一步建议
我们已经创建了能够稳定复现问题的最小化测试。现在，请运行 `pytest packages/cascade-engine/tests/integration/test_vm_strategy_lifecycle.py`。测试将会因为 `asyncio.TimeoutError` 而失败。

一旦确认了这个 RED 状态，我将生成下一个计划，重构 `VMExecutionStrategy` 来修复这个死锁。

---

好的，分析完毕。你的判断非常准确，没有任何日志输出意味着执行流程在进入我们植入日志的`_run_job`之前就已经卡住了。

### 战略分析：根本性设计缺陷

经过深入分析，我发现了一个比 `Jump` 信号翻译错误更底层的、致命的设计缺陷：

**`VMExecutionStrategy` 错误地 `await reactor.run()`，而 `reactor.run()` 被设计成一个永不退出的无限循环。**

这就是测试挂起（hang）的直接原因。

让我们梳理一下这个死锁的形成过程：

1.  `Engine.run()` 调用并 `await strategy.execute(...)`。
2.  `strategy.execute()` 启动了 `reactor.run()`，然后 `await` 它。
3.  `reactor.run()` 是一个 `while True:` 循环，它在处理完当前所有事件后，会 `await self._activity_signal.wait()`，进入休眠，**但它绝不会自行退出**。
4.  因此，`strategy.execute()` 永远被阻塞在 `await reactor.run()` 这一行，永远不会返回。
5.  `Engine.run()` 也因此永远不会返回。测试挂起。

**结论**：我们当前的策略层实现了一个“只进不出”的黑洞。它知道如何启动物理引擎，但完全不知道如何判断“任务已完成”并从中脱离。

### 修正策略：从“同步等待”到“异步订阅”

为了修复这个根本性问题，我们需要改变 `VMExecutionStrategy` 的行为模式：

1.  **后台启动**: `reactor.run()` 必须作为一个后台任务 (`asyncio.create_task`) 启动，而不是被 `await`。
2.  **结果订阅**: `strategy.execute()` 在启动 `Reactor` 后，必须找到一种方法来**订阅**最终的结果。最直接的方法是 `await` 一个 `asyncio.Event`，这个 `Event` 将在目标 `DataNode` 接收到结果时被设置。
3.  **优雅关闭**: 一旦结果事件被触发，`strategy.execute()` 就必须主动调用 `reactor.stop()` 来终止后台循环，然后从目标 `DataNode` 中提取并返回结果。

### 新的测试驱动计划

你的要求“创建新的测试”是完全正确的。当前的 TCO 测试过于复杂，它同时暴露了“生命周期管理”和“控制流编译”两个问题。我们将遵循 TDD 原则，先解决最基础的生命周期问题。

我将创建一个新的、更简单的测试文件，它只包含一个没有任何依赖或循环的简单任务。这个测试的**唯一目的**就是验证 `VMExecutionStrategy` 是否能正确地：
1.  启动 `Reactor`。
2.  等待任务完成。
3.  停止 `Reactor`。
4.  返回正确的结果。

这个失败的测试（它会因为挂起而失败）将精确地驱动我们去实现上述的“异步订阅”模式。

---

我将生成 Quipu 计划来创建这个新的测试文件。

