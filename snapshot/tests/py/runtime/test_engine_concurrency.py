import asyncio
import time
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from tests.py.runtime.test_engine_constraints import MockConnector, wait_for_task_finish


@pytest.mark.asyncio
async def test_engine_respects_concurrency_constraint(bus_and_spy):
    """
    Tests that tasks matching a concurrency constraint are executed with limited parallelism.
    """
    bus, spy = bus_and_spy
    mock_connector = MockConnector()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Define tasks. 'api_call' will be the constrained task.
    @cs.task
    async def api_call(i: int):
        await asyncio.sleep(0.1)  # Simulate network latency
        return i

    @cs.task
    def combine(results: list):
        return sorted(results)

    # 2. Define a workflow with 3 parallel api_calls
    # Without constraints, this would take ~0.1s
    calls = [api_call(i) for i in range(3)]
    workflow = combine(calls)

    # 3. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 4. Wait for the engine to connect and subscribe
    await asyncio.sleep(0.02)

    # 5. Inject a concurrency limit of 1 for 'api_call' tasks
    concurrency_scope = "task:api_call"
    concurrency_payload = {
        "id": "limit-api",
        "scope": concurrency_scope,
        "type": "concurrency",
        "params": {"limit": 1},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{concurrency_scope.replace(':', '/')}",
        concurrency_payload,
    )

    # 6. Measure execution time
    start_time = time.time()
    final_result = await run_task
    duration = time.time() - start_time

    # 7. Assertions
    assert final_result == [0, 1, 2]

    # With a limit of 1, the 3 tasks (0.1s each) must run sequentially.
    # Total time should be > 0.3s. We allow for a small margin.
    assert duration > 0.28, "Tasks did not run sequentially under concurrency limit"
    assert duration < 0.5, "Tasks took unexpectedly long"