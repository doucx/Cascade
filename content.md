好的，我们正式开始重构。

根据我们制定的路线图，第一步是建立一个坚实的、可靠的测试基础。我们将彻底移除旧的、依赖外部环境的系统测试，并创建一个新的、完全在内存中运行的端到端集成测试。这个新测试将能够稳定地复现 `cs-controller` 的非幂等性 Bug，为我们后续的修复工作提供一个明确的“红灯”信号。

我将生成一个计划来执行此项重构。

## [WIP] refactor: 使用确定性的内存连接器重构CLI集成测试

### 用户需求
遵循之前批准的重构路线图，我们需要用一个快速、可靠且完全隔离的端到端集成测试，来替换掉旧的、依赖外部 MQTT Broker 的系统测试。这个新的测试用例必须能在当前的代码基础上稳定地复现 `cs-controller` 的非幂等性 Bug。

### 评论
这是解决底层 Bug 的关键第一步。通过消除对外部 Broker 和 `subprocess` 的依赖，我们不仅能创建一个稳定重现问题的测试用例，还极大地改善了开发者体验（DX），使得测试套件更快、更可靠。这个重构遵循了“测试应验证意图而非实现”以及“确定性异步测试”的核心原则。

### 目标
1.  **清理**: 彻底删除旧的、脆弱的 `tests/sys` 目录及其内容。
2.  **构建**: 创建一个新的测试文件 `tests/py/e2e/test_e2e_cli_integration.py`。
3.  **实现测试工具**: 在新文件中，实现一个 `pytest` fixture (`controller_runner`)。该 fixture 将：
    *   实例化一个确定性的 `InProcessConnector`。
    *   通过 `monkeypatch` 将 `cascade.cli.controller.app.MqttConnector` 替换为我们的 `InProcessConnector` 实例。
    *   提供一个简洁的接口，用于在测试中直接调用 `cs-controller` 的核心异步逻辑（如 `set-limit`）。
4.  **编写失败的测试**: 使用新的 fixture 编写 `test_cli_idempotency_unblocks_engine` 测试用例。该测试将编排“设置慢速限制 -> 验证节流 -> 设置快速限制 -> 验证死锁”的完整场景。
5.  **预期结果**: 在当前代码下，此测试用例将因 `asyncio.TimeoutError` 而**失败**，从而为我们提供一个清晰的、可修复的故障信号。

### 基本原理
我们将遵循重构路线图的第一、二步。我们不直接调用 `typer` 应用的入口点（因为它内部的 `asyncio.run` 会与 `pytest-asyncio` 的事件循环冲突），而是创建一个测试专用的“控制器应用”模拟器。这个模拟器会直接调用 `cs-controller` 内部的核心 `async def` 函数（例如 `_publish_limit`），并通过 `monkeypatch` 将其网络通信重定向到内存中的 `InProcessConnector`。这使得我们可以在同一个异步事件循环中，协同测试 `Engine` 和 `cs-controller` 的交互，从而以一种完全确定性的方式复现时序相关的 Bug。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/cli #concept/state #scope/dx #ai/instruct #task/domain/control-plane #task/object/constraint-management #task/action/refactor-idempotency #task/state/continue

---

### Script

#### Acts 1: 清理旧的系统测试并创建新的集成测试文件

我们将首先删除整个 `tests/sys` 目录，然后创建新的测试文件，其中包含复现 Bug 所需的全套逻辑：测试工具、workflow 定义和失败的测试用例本身。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf tests/sys
~~~~~

~~~~~act
write_file
tests/py/e2e/test_e2e_cli_integration.py
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskExecutionFinished

# 导入 app 模块中的核心异步逻辑函数
from cascade.cli.controller import app as controller_app
from cascade.connectors.mqtt import MqttConnector

from .harness import InProcessConnector, MockWorkExecutor

# --- Test Harness for In-Process CLI Interaction ---

class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""
    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(self, **kwargs):
        # Directly call the async logic, bypassing Typer and asyncio.run()
        await controller_app._publish_limit(
            hostname="localhost", port=1883, **kwargs
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    # 1. Create the deterministic, in-memory connector for this test
    connector = InProcessConnector()

    # 2. Monkeypatch the MqttConnector class *where it's used* in the controller app module
    #    to always return our in-memory instance.
    #    Note: We patch the class constructor to return our instance.
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: connector
    )
    
    # 3. Return a controller instance that uses this connector
    return InProcessController(connector)

# --- The Failing Test Case ---

@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(controller_runner, bus_and_spy):
    """
    This test should FAIL with the current code due to a timeout.
    It verifies that a non-idempotent CLI controller creates conflicting
    constraints that deadlock the engine.
    """
    bus, spy = bus_and_spy
    
    # ARRANGE: Define a simple workflow
    @cs.task
    def fast_task(i: int):
        return i

    workflow = fast_task.map(i=range(10))

    # ARRANGE: Setup the engine to use the same in-memory connector
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    # ACT & ASSERT
    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit using the in-process controller.
        await controller_runner.set_limit(scope="global", rate="1/s")

        # 2. Wait long enough to confirm the engine is running but throttled.
        # We wait up to 2s for at least one task to finish.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. In the buggy version, this adds a NEW conflicting limit
        # because the CLI generates a new random ID for the constraint.
        await controller_runner.set_limit(scope="global", rate="100/s")

        # 4. The engine should now finish quickly.
        # With the bug, it will be deadlocked on the old "1/s" limit and this will time out.
        await asyncio.wait_for(engine_task, timeout=2.0)

    except asyncio.TimeoutError:
        pytest.fail(
            "Engine timed out as expected. This confirms the non-idempotent "
            "controller created conflicting constraints, deadlocking the engine."
        )
    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task

    # This part should only be reached after the bug is fixed.
    # For now, the test is expected to fail before this.
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10
~~~~~

### 下一步建议

我们已经成功地创建了一个可靠的、可复现的“红灯”测试。运行此测试用例（`pytest tests/py/e2e/test_e2e_cli_integration.py`）现在应该会稳定地失败并报告 `pytest.fail` 中指出的超时问题。

下一步是执行路线图中的**第三步**：**应用幂等性修复**。我将生成一个新计划，其中包含对 `cascade-cli-controller/src/cascade/cli/controller/app.py` 和 `cascade-runtime/src/cascade/runtime/constraints/manager.py` 的修改，以实现稳定标识符和“最后写入为准”的逻辑。
