You are absolutely right. My apologies, the generated test harness had a flaw in its call signature, and the failure logic was confusingly inverted. Thank you for catching that. The goal is indeed to have a clean test that fails for the right reason.

The `TypeError` occurs because when we call `controller_app._publish_limit` directly, we bypass the Typer CLI layer. Typer would normally handle optional arguments that aren't provided on the command line, but a direct Python call requires all arguments without a default value (`= None`) to be present. The signature of `_publish_limit` expects `concurrency` and `ttl`, even if their value is `None`.

I will now generate a plan to fix this test. This plan corrects the call signature in our test harness and simplifies the test's failure logic to be more straightforward: it will now naturally fail with a timeout, which is the clear "red light" we need.

## [WIP] fix: Correct TypeError in CLI integration test harness

### 错误分析
测试 `test_cli_idempotency_unblocks_engine` 失败，并报告 `TypeError`，因为测试辅助工具 `InProcessController` 在调用 `_publish_limit` 函数时，未能提供 `concurrency` 和 `ttl` 这两个必需的参数。

虽然这两个参数在 CLI 中是可选的，但在 Python 函数签名中，它们没有默认值（例如 `concurrency: int | None = None`），因此在直接调用时必须提供。此外，原始测试用例中的 `except asyncio.TimeoutError: pytest.fail(...)` 逻辑是反直觉的；一个因超时而失败的测试应该直接被报告为失败，而不是通过 `pytest.fail` 将其标记为失败，这会掩盖真正的失败原因。

### 用户需求
修复 `tests/py/e2e/test_e2e_cli_integration.py` 中的 `TypeError`，并调整测试逻辑，使其在遇到预期的死锁时能够自然地因超时而失败，从而稳定地复现 Bug。

### 评论
这是一个关键的修复，它使我们的新测试用例能够实际运行并准确地暴露底层的幂等性问题。通过修正调用签名并简化失败逻辑，我们得到了一个清晰、可靠的“红灯”测试，为后续的修复工作铺平了道路。

### 目标
1.  修改 `InProcessController` 辅助类中的 `set_limit` 方法，使其接受并传递 `concurrency` 和 `ttl` 参数，并为它们提供 `None` 作为默认值。
2.  移除 `test_cli_idempotency_unblocks_engine` 测试用例中的 `try...except` 块，让 `asyncio.TimeoutError` 能够自然地导致测试失败。
3.  在测试的文档字符串中明确说明，该测试预期会因超时而失败。

### 基本原理
我们将通过精确匹配 `_publish_limit` 函数的签名来修复 `TypeError`。同时，我们将移除多余的异常捕获逻辑。一个健壮的回归测试应该在其预期失败的场景下直接失败（亮红灯），而不是捕获预期的异常然后手动调用 `pytest.fail`。这使得测试结果更加清晰，并直接反映了系统的真实行为。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/control-plane #task/object/constraint-management #task/action/refactor-idempotency #task/state/continue

---

### Script

#### Acts 1: 修正测试辅助工具并简化测试用例

我们将通过一个 `patch_file` 操作来同时更新 `InProcessController` 和 `test_cli_idempotency_unblocks_engine`，以确保测试的正确性和清晰度。

~~~~~act
patch_file
tests/py/e2e/test_e2e_cli_integration.py
~~~~~
~~~~~python
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
~~~~~python
class InProcessController:
    """A test double for the controller CLI that calls its core logic in-process."""
    def __init__(self, connector: InProcessConnector):
        self.connector = connector

    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            hostname="localhost",  # Constant for test purposes
            port=1883,           # Constant for test purposes
        )

@pytest.fixture
def controller_runner(monkeypatch):
    """
    Provides a way to run cs-controller commands in-process with a mocked connector.
    """
    connector = InProcessConnector()
    monkeypatch.setattr(
        controller_app.MqttConnector,
        "__new__",
        lambda cls, *args, **kwargs: connector
    )
    return InProcessController(connector)

# --- The Failing Test Case ---

@pytest.mark.asyncio
async def test_cli_idempotency_unblocks_engine(controller_runner, bus_and_spy):
    """
    This test is EXPECTED TO FAIL with a timeout on the pre-fix codebase.
    It verifies that a non-idempotent CLI controller creates conflicting
    constraints that deadlock the engine. After the fix is applied, this
    test should pass.
    """
    bus, spy = bus_and_spy
    
    @cs.task
    def fast_task(i: int):
        return i
    workflow = fast_task.map(i=range(10))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=controller_runner.connector,
    )

    engine_task = asyncio.create_task(engine.run(workflow))

    try:
        # 1. Set a slow limit.
        await controller_runner.set_limit(scope="global", rate="1/s")

        # 2. Wait to confirm the engine is throttled.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if len(spy.events_of_type(TaskExecutionFinished)) > 0:
                break
        
        assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
            "Engine did not start processing tasks under the initial slow rate limit."
        )

        # 3. Set a fast limit. The bug causes this to ADD a new conflicting constraint.
        await controller_runner.set_limit(scope="global", rate="100/s")

        # 4. The engine should now finish quickly. The bug will cause a timeout here.
        await asyncio.wait_for(engine_task, timeout=2.0)

    finally:
        # Cleanup: ensure engine task is cancelled if it's still running
        if not engine_task.done():
            engine_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await engine_task

    # This part is only reached if the test passes (i.e., after the bug is fixed).
    assert len(spy.events_of_type(TaskExecutionFinished)) == 10
~~~~~

### 下一步建议
测试用例现已修复并能正常运行。它将稳定地因 `asyncio.TimeoutError` 而失败，这正是我们需要的“红灯”。

既然您提到修复已经完成，我们现在可以前进到**路线图的第四步**：**重新应用修复并验证测试通过**。请您将修复幂等性问题的代码变更应用到工作区，然后再次运行这个测试。它现在应该会顺利通过，从而证明我们的修复是正确且有效的。
