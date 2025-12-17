import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_resource_concurrency_limit():
    """
    Test that system capacity limits task concurrency.
    We set up a system with 'slots=1', and try to run 2 tasks in parallel that each require 'slots=1'.
    They should execute sequentially, doubling the total time.
    """

    @cs.task
    async def slow_task(name: str):
        # Simulate work
        await asyncio.sleep(0.1)
        return time.time()

    # Define two parallel tasks
    t1 = slow_task("t1").with_constraints(slots=1)
    t2 = slow_task("t2").with_constraints(slots=1)

    # Run them (we need a way to run both, creating a list)
    @cs.task
    def gather(a, b):
        return a, b

    workflow = gather(t1, t2)

    start_time = time.time()

    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    # FIX: Use Engine directly to avoid nested event loop error in tests
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"slots": 1},
    )
    result = await engine.run(workflow)

    duration = time.time() - start_time
    t1_end, t2_end = result

    # In parallel, it would take ~0.1s. In serial, ~0.2s.
    # Allow some buffer for overhead.
    assert duration >= 0.2

    # One must finish before the other, roughly.
    assert abs(t1_end - t2_end) >= 0.1


@pytest.mark.asyncio
async def test_dynamic_resource_constraint():
    """
    Test that a task can request resources based on an upstream calculation.
    """

    @cs.task
    def calculate_cpu_needs():
        return 2

    @cs.task
    def cpu_heavy_task():
        return "Done"

    # CPU needs are determined dynamically
    needs = calculate_cpu_needs()

    # The task requests 'cpu' equal to the result of 'needs' (2)
    job = cpu_heavy_task().with_constraints(cpu=needs)

    # We set system capacity to 4.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"cpu": 4},
    )
    result = await engine.run(job)

    assert result == "Done"


@pytest.mark.asyncio
async def test_insufficient_resources_deadlock():
    """
    Test that requesting more resources than available raises an error immediately
    (feasibility check), rather than hanging indefinitely.
    """

    @cs.task
    def massive_job():
        return "Should not run"

    job = massive_job().with_constraints(memory_gb=64)

    # System only has 16GB
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        system_resources={"memory_gb": 16},
    )

    with pytest.raises(ValueError, match="exceeds total system capacity"):
        await engine.run(job)
