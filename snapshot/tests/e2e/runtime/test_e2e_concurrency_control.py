import time
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.runtime.kernel.solvers.native import NativeSolver
from cascade.runtime.host.instance import Engine
from cascade.runtime import EventBus
from cascade.spec.constraint import GlobalConstraint

# Use the deterministic Mock infrastructure from the SDK
from cascade.testing import MockExecutor, MockConnector


@pytest.mark.asyncio
async def test_e2e_concurrency_control():
    """
    Full end-to-end test with Retained Messages.
    1. Controller state is pre-seeded (Retained).
    2. Engine starts, connects, receives config immediately, AND THEN executes.
    """
    # 1. Setup deterministic connector
    connector = MockConnector()

    # 2. Pre-seed the constraint (Simulating existing environment config)
    # Instead of "acting" (publishing), we "arrange" (seed state).
    # This prevents race conditions where the publish might not be processed
    # before the engine starts tasks.
    constraint = GlobalConstraint(
        id="concurrency-task:slow_task-fixed",
        scope="task:slow_task",
        type="concurrency",
        params={"limit": 1},
    )
    # The topic format usually follows MQTT conventions: cascade/constraints/<scope_path>
    topic = "cascade/constraints/task/slow_task"
    connector.seed_retained_message(topic, asdict(constraint))

    # 3. Define the workflow
    @cs.task
    def slow_task(x):
        return x

    # 4 tasks that would normally run in parallel in ~0.05s
    # Total work = 4 * 0.05s = 0.20s
    workflow = slow_task.map(x=[1, 2, 3, 4])

    # 4. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=EventBus(),
        connector=connector,
    )

    # 5. Run the engine
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    # 6. Assertions
    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1 (serial execution):
    # Expected time >= 4 * 0.05 = 0.20s.
    # Allowing for slight overhead or timer grit, 0.18s is a safe lower bound
    # to distinguish from parallel execution (which would be ~0.05s).
    assert duration >= 0.18, (
        f"Expected serial execution (~0.2s), but took {duration:.4f}s. "
        "Concurrency constraint may not have been applied."
    )
