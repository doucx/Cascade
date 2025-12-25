You are absolutely right. My apologies. My previous refactoring plan was incomplete. I removed `MockWorkExecutor` from `harness.py` but failed to identify and update two other test files that were still importing and using it. This is a classic dependency issue.

The test collection errors are a direct result of this oversight. I will now generate a plan to fix these import errors and complete the refactoring.

## [WIP] fix: Resolve import errors by refactoring remaining MockWorkExecutor usages

### 错误分析
The previous refactoring plan removed `MockWorkExecutor` from `tests/e2e/runtime/harness.py` but failed to update two other test files (`test_e2e_runtime_control_updates.py` and `test_e2e_ttl.py`) that still depended on it. This resulted in an `ImportError` during pytest's test collection phase, as the import target no longer exists.

### 用户需求
Fix the test collection errors by completing the refactoring of all `Executor` test doubles.

### 评论
This is a necessary cleanup step to complete the previous refactoring. It highlights the importance of identifying all dependencies before removing a shared component. By fixing these final two files, we will achieve a fully consistent test suite.

### 目标
1.  Modify `tests/e2e/runtime/test_e2e_runtime_control_updates.py` to import and use the standardized `MockExecutor` from `cascade.testing`.
2.  Modify `tests/e2e/runtime/test_e2e_ttl.py` to do the same, thus resolving all import errors.

### 基本原理
The strategy is to complete the work started in the previous step. By replacing the last remaining usages of the specialized `MockWorkExecutor` with the standardized `MockExecutor` from `cascade.testing`, we will resolve the import errors and finalize the test infrastructure cleanup. We will use `write_file` for each affected file to ensure the imports and instantiations are corrected.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-doubles #task/action/refactor #task/state/end

---
### Script

#### Acts 1: Refactor control updates test

We will update `test_e2e_runtime_control_updates.py` to use the correct, centralized `MockExecutor`.

~~~~~act
write_file
tests/e2e/runtime/test_e2e_runtime_control_updates.py
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict
import uuid

from .harness import InProcessConnector
from cascade.testing import MockExecutor


async def set_rate_limit(
    connector: InProcessConnector, scope: str, rate: str, constraint_id: str = None
):
    """Helper to publish a rate limit constraint."""
    if not constraint_id:
        constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
    constraint = GlobalConstraint(
        id=constraint_id,
        scope=scope,
        type="rate_limit",
        params={"rate": rate},
    )
    payload = asdict(constraint)
    topic = f"cascade/constraints/{scope.replace(':', '/')}"
    await connector.publish(topic, payload, retain=True)


@pytest.mark.asyncio
async def test_updating_rate_limit_unblocks_engine(bus_and_spy):
    """
    Regression test for the rate-limit update deadlock.
    Verifies that updating a slow rate limit to a fast one wakes up a sleeping
    engine and allows it to proceed at the new rate.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()

    # ARRANGE
    @cs.task
    def fast_task(i: int):
        return i

    # A workflow with enough tasks to clearly see the rate limit effect
    workflow = fast_task.map(i=range(5))

    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
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
    for _ in range(20):  # Give it 2 seconds to finish the first task
        await asyncio.sleep(0.1)
        if len(spy.events_of_type(TaskExecutionFinished)) > 0:
            break

    assert len(spy.events_of_type(TaskExecutionFinished)) >= 1, (
        "Engine did not start processing tasks under the initial slow rate limit."
    )

    # Now, publish a very fast rate limit using the SAME ID. This should unblock the engine.
    await set_rate_limit(
        connector, scope="global", rate="100/s", constraint_id=limit_id
    )

    # The engine should now wake up and finish the remaining ~4 tasks very quickly.
    # If it's deadlocked, this await will time out.
    try:
        results = await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail(
            "Engine deadlocked and did not respond to the updated rate limit within the timeout."
        )

    # Final verification
    assert sorted(results) == [0, 1, 2, 3, 4]
    assert len(spy.events_of_type(TaskExecutionFinished)) == 5
~~~~~

#### Acts 2: Refactor TTL test

Similarly, we will update `test_e2e_ttl.py` to resolve the final import error.

~~~~~act
write_file
tests/e2e/runtime/test_e2e_ttl.py
~~~~~
~~~~~python
import time
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockExecutor

from .harness import InProcessConnector


@pytest.mark.asyncio
async def test_e2e_ttl_expiration():
    """
    Tests that a pause constraint automatically expires after TTL.
    """
    connector = InProcessConnector()

    # Helper to avoid complex harness logic for now
    from cascade.spec.constraint import GlobalConstraint
    from dataclasses import asdict
    import uuid

    async def pause_with_ttl(scope: str, ttl: float):
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
    def simple_task():
        return True

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
    def simple_task():
        return True

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    start_time = time.time()

    # 2. Run engine. It should be paused initially.
    # The Engine loop will wait on wakeup.
    # ConstraintManager should have scheduled a wakeup at T+0.25s.
    # At T+0.25s, Engine wakes up, cleans expired constraint, and unblocks.
    await engine.run(workflow)

    duration = time.time() - start_time

    # 3. Assertions
    # Duration must be at least the TTL (0.25s), proving it was blocked.
    assert duration >= 0.24, f"Engine didn't wait for TTL! Duration: {duration:.3f}s"

    # But it shouldn't wait forever (e.g. < 1s)
    assert duration < 1.0, "Engine waited too long or didn't recover."
~~~~~
