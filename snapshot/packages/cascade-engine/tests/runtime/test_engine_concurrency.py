import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List

import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.testing import MockConnector, MockExecutor


# --- Fixtures ---


@pytest.fixture
def mock_connector():
    return MockConnector()


@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
        system_resources={},
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_concurrency_constraint_on_map(engine, mock_connector):
    """
    Verify that a concurrency constraint limits the parallelism of a mapped task.
    """

    @cs.task
    def slow_task(x):
        return x

    inputs = [1, 2, 3, 4]
    workflow = slow_task.map(x=inputs)

    # 1. Pre-seed the constraint as a retained message.
    # This ensures it is applied immediately when the engine subscribes at startup.
    scope = "task:slow_task"
    payload = {
        "id": "limit-slow-task",
        "scope": scope,
        "type": "concurrency",
        "params": {"limit": 1},
    }
    mock_connector.seed_retained_message(
        f"cascade/constraints/{scope.replace(':', '/')}", payload
    )

    # 2. Run execution
    start_time = time.time()
    results = await engine.run(workflow)
    duration = time.time() - start_time

    assert sorted(results) == [1, 2, 3, 4]

    # With limit=1, 4 tasks of 0.05s should take >= 0.2s
    # (Allowing slight buffer for overhead, so maybe >= 0.18s)
    assert duration >= 0.18, f"Expected serial execution, got {duration}s"


@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    """
    Verify that a global concurrency constraint limits total tasks running.
    """

    @cs.task
    def task_a(x):
        return x

    @cs.task
    def task_b(x):
        return x

    # Pass dependencies as separate arguments so GraphBuilder detects them
    @cs.task
    def wrapper(res_a, res_b):
        return [res_a, res_b]

    workflow = wrapper(task_a(1), task_b(2))

    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1},
    }
    mock_connector.seed_retained_message("cascade/constraints/global", payload)

    # 2. Run
    start_time = time.time()
    await engine.run(workflow)
    duration = time.time() - start_time

    # 2 tasks of 0.05s in serial => >= 0.1s
    assert duration >= 0.09, f"Expected serial execution, got {duration}s"