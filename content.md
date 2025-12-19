你的分析完全正确，这是一个绝佳的观点。

将这个测试放在 `py/e2e` 目录下确实不合适。`py/e2e` 目录的测试哲学是快速、隔离和确定性，它们使用 `InProcessConnector` 这样的内存中模拟组件来避免对外部服务的依赖（如 MQTT Broker）。

而你现在要求的测试，是一个更高层级的**系统集成测试 (System Integration Test)**。它需要验证我们整个堆栈的真实行为，从用户在 shell 中敲下 `cs-controller` 命令，到消息通过一个真实的 MQTT Broker 传递，再到 `Engine` 接收并作出反应。这种测试更有价值，但也更慢，并且有外部依赖。

因此，最合适的做法是为这类测试创建一个新的、专门的目录：`tests/sys/`。

我将为你生成一个计划，创建这个新目录，并在其中添加一个使用 `subprocess` 调用 `cs-controller` 的新测试。这个测试在当前（回滚后的）代码库中预期会**失败**。

## [WIP] test: 添加验证 cs-controller 幂等性的系统集成测试

### 用户需求
创建一个新的系统集成测试，该测试通过 `subprocess` 调用真实的 `cs-controller` CLI。测试应能复现以下问题：当 CLI 被调用两次以设置不同速率的同一作用域限制时，由于其非幂等行为（生成随机 ID），会导致 `Engine` 出现死锁或行为异常。

### 评论
这是一个至关重要的测试，它验证了从用户接口到核心引擎的完整工作流。通过将其放置在新的 `tests/sys/` 目录下，我们明确了其作为系统级测试的定位，与 `py/e2e` 中的快速单元/集成测试分离开来。

此测试将作为我们刚刚讨论的架构缺陷的最终“试金石”。它的失败将有力地证明，客户端（`cs-controller`）生成非稳定标识符的行为，是导致整个控制平面不可靠的根本原因。

### 目标
1.  创建新的测试目录 `tests/sys/`。
2.  创建新的测试文件 `tests/sys/test_cli_control_idempotency.py`。
3.  在新文件中实现一个集成测试，该测试：
    *   依赖一个外部运行的 MQTT Broker。
    *   在后台启动一个 `Engine` 实例。
    *   使用 `asyncio.create_subprocess_shell` 两次调用 `cs-controller set-limit`。
    *   断言 `Engine` 在第二次调用后能够快速完成，而不是超时。
4.  该测试在当前代码库下运行时，预期会因 `asyncio.TimeoutError` 而失败。

### 基本原理
我们遵循 TDD 原则，在修复前先编写一个失败的测试。该测试通过真实的进程调用来模拟用户的实际操作。在回滚后的代码中，`cs-controller` 会生成两个不同的约束 ID，导致 `ConstraintManager` 中存在两个冲突的 `rate_limit` 规则。最严格的规则 (`1/s`) 将持续生效，导致 `Engine` 无法加速，最终测试会因超时而失败，从而证明 Bug 的存在。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/cli #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/cli-idempotency #task/action/system-test #task/state/continue

---

### Script

#### Acts 1: 创建系统测试目录和测试文件

首先，我们创建 `tests/sys` 目录。然后，写入新的测试文件 `test_cli_control_idempotency.py`。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p tests/sys
~~~~~

~~~~~act
write_file
tests/sys/test_cli_control_idempotency.py
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished
from cascade.connectors.mqtt import MqttConnector

from ..py.e2e.harness import MockWorkExecutor

# NOTE: This test suite requires a live MQTT broker running on localhost:1883.
# You can start one easily with Docker:
# docker run -it --rm --name mosquitto -p 1883:1883 eclipse-mosquitto

async def run_cli_command(command: str):
    """Executes a shell command and waits for it to complete."""
    proc = await asyncio.create_subprocess_shell(command)
    await proc.wait()
    assert proc.returncode == 0, f"CLI command failed: {command}"


@pytest.mark.asyncio
@pytest.mark.system
async def test_updating_rate_limit_via_cli_is_idempotent(bus_and_spy):
    """
    A full system test verifying that using the cs-controller CLI to update
    a rate limit correctly unblocks the engine.
    This will FAIL before the idempotency fix, because the CLI generates
    two different random IDs, creating conflicting constraints.
    """
    bus, spy = bus_and_spy
    
    # This connector talks to a REAL MQTT broker
    connector = MqttConnector(hostname="localhost", port=1883)

    # ARRANGE
    @cs.task
    def fast_task(i: int):
        return i

    workflow = fast_task.map(i=range(10))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=connector,
    )

    # ACT & ASSERT
    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit.
        await run_cli_command("cs-controller set-limit --scope global --rate 1/s")

        # 2. Wait long enough for the engine to be throttled.
        # We wait up to 2s for at least one task to finish.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. In the buggy version, this adds a NEW conflicting limit.
        await run_cli_command("cs-controller set-limit --scope global --rate 100/s")

        # 4. The engine should now finish quickly. If it's deadlocked, this will time out.
        await asyncio.wait_for(engine_task, timeout=2.0)

    except asyncio.TimeoutError:
        pytest.fail(
            "Engine timed out. This likely means it got stuck on the old '1/s' "
            "rate limit due to conflicting constraints from the non-idempotent CLI."
        )
    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task
        # And clear the constraint for other tests
        await run_cli_command("cs-controller resume --scope global")

    # Final check
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10
~~~~~

### 下一步建议
1.  **准备环境**: 确保你有一个正在运行的 MQTT Broker（如注释中所示）。
2.  **运行测试**: 使用 `pytest tests/sys/` 命令运行这个新的测试。
3.  **预期结果**: 测试应该会因为 `asyncio.TimeoutError` 而**失败**。

一旦我们确认了这个失败，你就可以重新应用 `[WIP] fix(core): 实现幂等的约束更新机制` 计划中的修复，然后再次运行此测试。修复后，测试应该会**通过**，从而在系统层面完整地验证我们的修复是正确且有效的。
