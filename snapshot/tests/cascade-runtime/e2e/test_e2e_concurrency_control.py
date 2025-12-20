import asyncio
import time
from typing import Dict, Any, List
import uuid
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.interfaces.protocols import Node, Executor

from .harness import InProcessConnector


# Override harness executor to simulate specific timing for this test
class SlowWorkExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        await asyncio.sleep(0.05)
        if kwargs:
            return next(iter(kwargs.values()))
        return "result"


@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller publishes constraint (Retained).
    2. Engine starts, connects, receives config, AND THEN executes.
    """
    # 1. Setup shared communication bus
    connector = InProcessConnector()

    # 2. Setup the Controller (simulated by manual publish helper in this test context if needed,
    # or using the simplified helper from harness but constructing payload manually as in original test)
    # The ControllerTestApp in harness is generic. We can extend it or use it.
    # The original test had set_concurrency_limit helper. Let's replicate or inline it.

    # Inline setting concurrency limit using standard controller app logic
    # But wait, harness ControllerTestApp only has pause/resume.
    # Let's use the connector directly or update harness later?
    # To keep this atomic, I'll just publish via connector here or extend ControllerTestApp locally if needed.
    # Actually, let's just do manual publish to keep it simple as in harness.

    # To avoid changing harness too much in Acts 1, I will implement helper here.
    from cascade.spec.constraint import GlobalConstraint

    async def set_concurrency_limit(scope: str, limit: int):
        constraint = GlobalConstraint(
            id=f"concurrency-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="concurrency",
            params={"limit": limit},
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await connector.publish(topic, payload, retain=True)

    # 3. Publish the constraint FIRST (Simulating existing environment config)
    # Limit task concurrency to 1
    await set_concurrency_limit(scope="task:slow_task", limit=1)

    # 4. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=SlowWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    # 6. Run the engine
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    # 7. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s.
    assert duration >= 0.18, (
        f"Expected serial execution (~0.2s), but took {duration:.4f}s"
    )
