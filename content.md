好的，我们进入 **里程碑 1.4**，为“感知原语” `cs.recv` 编写 TDD 测试。

关于命名，`cs.recv` 是一个简洁且符合“接收/发送”对称性的好名字，它清晰地表达了“接收一个信号”的意图。我将沿用这个名称。

现在，我们将创建测试套件，进入 **Red** 阶段。由于 `cs.recv` 提供者尚不存在，这些测试会因 `AttributeError` 而失败，从而为我们的实现提供明确的目标。

## [WIP] test(providers): 为信号原语 cs.recv 添加 TDD 测试

### 用户需求
根据“萤火计划” Milestone 1.4，为 `cs.recv` 原子任务创建 TDD 测试套件。
测试需覆盖以下核心功能：
1.  **异步唤醒**: 验证 `cs.recv` 能够挂起一个工作流的执行，直到从 `Connector` 接收到匹配主题的信号，然后恢复执行。
2.  **超时与回退**: 验证 `cs.recv` 在指定时间内未收到信号时，会抛出 `asyncio.TimeoutError` 异常，从而允许工作流实现容错和回退逻辑。

### 评论
`cs.recv` 是 Cascade Agent 的“耳朵”，是实现响应式行为的基石。它将外部世界的事件（通过 `Connector` 传入）转化为工作流内部的控制流。这两个测试用例精确地定义了 `cs.recv` 的核心行为契约：等待与超时。

### 目标
创建 `tests/py/providers/test_signal_provider.py` 文件，并包含 `test_recv_blocks_and_wakes_up` 和 `test_recv_times_out` 两个预期失败的测试。

### 基本原理
我们将使用 `LocalBusConnector` 作为测试的确定性信令总线。
*   `test_recv_blocks_and_wakes_up`: 在后台运行一个包含 `cs.recv` 的工作流，然后通过 `LocalBusConnector` 发布一个匹配的信号，并断言工作流最终成功完成。
*   `test_recv_times_out`: 运行一个带 `timeout` 参数的 `cs.recv` 工作流，但不发布任何信号。断言 `asyncio.TimeoutError` 被正确抛出，且执行耗时约等于超时时长。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/core #concept/signal #scope/api #ai/instruct #task/domain/providers #task/object/recv-primitive #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建 `cs.recv` 的 TDD 测试套件

我们将创建一个新的测试文件，`tests/py/providers/test_signal_provider.py`。

~~~~~act
write_file
tests/py/providers/test_signal_provider.py
~~~~~
~~~~~python
import asyncio
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.connectors.local import LocalBusConnector


@pytest.fixture
def local_connector():
    """Provides a fresh LocalBusConnector for each test."""
    return LocalBusConnector()


@pytest.fixture
def engine(local_connector):
    """Provides an engine instance configured with a LocalBusConnector."""
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        connector=local_connector,
    )


@pytest.mark.asyncio
async def test_recv_blocks_and_wakes_up(engine, local_connector):
    """
    Test Case 8 (From Firefly Plan): Asynchronous Wake-up.

    Verifies that a task executing cs.recv pauses until a matching signal
    is published on the connector, at which point it resumes.
    """
    topic = "firefly/sync/pulse"
    payload = {"source": "firefly-01"}

    @cs.task
    def downstream_task(signal):
        return signal  # signal should be the received payload

    workflow = downstream_task(cs.recv(topic))

    # Run the engine in a background task
    engine_task = asyncio.create_task(engine.run(workflow))

    # Give the engine a moment to start and block on recv()
    await asyncio.sleep(0.05)
    assert not engine_task.done(), "Engine finished prematurely before signal was sent"

    # Publish the signal that should unblock the workflow
    await local_connector.publish(topic, payload)

    # Await the final result
    final_result = await asyncio.wait_for(engine_task, timeout=1.0)

    assert final_result == payload


@pytest.mark.asyncio
async def test_recv_times_out(engine):
    """
    Test Case 9 (From Firefly Plan): Timeout and Fallback.

    Verifies that cs.recv raises TimeoutError if a signal is not received
    within the specified timeout period.
    """
    topic = "firefly/no-reply"
    timeout_duration = 0.05

    workflow = cs.recv(topic, timeout=timeout_duration)

    start_time = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await engine.run(workflow)
    duration = time.time() - start_time

    # Verify that the timeout was respected
    assert timeout_duration <= duration < timeout_duration + 0.05, (
        f"Timeout was not respected. Expected ~{timeout_duration}s, took {duration:.2f}s."
    )

~~~~~

### 下一步建议
运行测试。由于 `cs.recv` 不存在，测试会失败。确认失败后，我将生成实现 `cs.recv` 提供者的计划，该计划将涉及与 `Engine` 的 `Connector` 协议进行交互。
