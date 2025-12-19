这是一个 `[WIP]` 计划，包含文件修改。

## [WIP] fix(test): 在速率限制更新测试中使用稳定的约束 ID

### 用户需求
修改 `tests/py/e2e/test_e2e_runtime_control_updates.py`，确保在更新速率限制时使用相同的 `constraint_id`。

### 评论
在之前的测试失败分析中，我们发现测试辅助函数 `set_rate_limit` 每次调用都会生成一个新的随机 UUID。这意味着第二次调用实际上是**添加了第二个**约束，而不是更新现有的约束。这会导致 `RateLimiter` 被双重扣费（虽然桶是共享的），引入了不必要的复杂性。为了验证“更新约束能解开死锁”这一核心假设，我们需要确保操作是真正的“更新”。

### 目标
1.  修改 `set_rate_limit` 辅助函数，接受一个可选的 `constraint_id`。
2.  在测试用例中，生成一个固定的 ID，并在两次调用 `set_rate_limit` 时传入该 ID。

### 基本原理
控制变量法。我们需要排除“多重约束叠加”这一干扰因素，专注于验证 `Engine` 在接收到约束参数变更（Rate: 1/s -> 100/s）时的响应行为。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/engine-control #task/action/fix-test-logic #task/state/continue

---

### Script

#### Acts 1: 修改测试以使用固定 ID

~~~~~act
patch_file
tests/py/e2e/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python
async def set_rate_limit(connector: InProcessConnector, scope: str, rate: str):
    """Helper to publish a rate limit constraint."""
    constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
    constraint = GlobalConstraint(
        id=constraint_id,
        scope=scope,
        type="rate_limit",
        params={"rate": rate},
    )
~~~~~
~~~~~python
async def set_rate_limit(connector: InProcessConnector, scope: str, rate: str, constraint_id: str = None):
    """Helper to publish a rate limit constraint."""
    if not constraint_id:
        constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
    constraint = GlobalConstraint(
        id=constraint_id,
        scope=scope,
        type="rate_limit",
        params={"rate": rate},
    )
~~~~~

~~~~~act
patch_file
tests/py/e2e/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=connector,
    )

    # Publish a very slow rate limit *before* starting
    await set_rate_limit(connector, scope="global", rate="1/s")

    # ACT & ASSERT
    run_task = asyncio.create_task(engine.run(workflow))

    # Wait for the first task to finish, confirming the engine is running and throttled
    for _ in range(20): # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break
    
    assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
        "Engine did not start processing tasks under the initial slow rate limit."
    )

    # Now, publish a very fast rate limit. This should unblock the engine.
    await set_rate_limit(connector, scope="global", rate="100/s")

    # The engine should now wake up and finish the remaining ~4 tasks very quickly.
~~~~~
~~~~~python
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=bus,
        connector=connector,
    )

    # Use a fixed ID to simulate an UPDATE, not adding a second constraint
    limit_id = "global-rate-limit-1"

    # Publish a very slow rate limit *before* starting
    await set_rate_limit(connector, scope="global", rate="1/s", constraint_id=limit_id)

    # ACT & ASSERT
    run_task = asyncio.create_task(engine.run(workflow))

    # Wait for the first task to finish, confirming the engine is running and throttled
    for _ in range(20): # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break
    
    assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
        "Engine did not start processing tasks under the initial slow rate limit."
    )

    # Now, publish a very fast rate limit using the SAME ID. This should unblock the engine.
    await set_rate_limit(connector, scope="global", rate="100/s", constraint_id=limit_id)

    # The engine should now wake up and finish the remaining ~4 tasks very quickly.
~~~~~

### 下一步建议
再次运行测试。
- 如果通过，说明问题确实在于多重约束的干扰，我们随后需要单独评估是否需要修复多重约束的行为，或者只是规范 CLI 的 ID 生成逻辑。但无论如何，Engine 的核心唤醒机制被证明是有效的。
- 如果依然失败，那么我们就可以确信问题出在 `Engine` 的唤醒逻辑本身，必须深入代码进行修复。
