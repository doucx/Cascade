import time
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus

from .harness import InProcessConnector, MockWorkExecutor


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
        executor=MockWorkExecutor(),
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
        executor=MockWorkExecutor(),
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
