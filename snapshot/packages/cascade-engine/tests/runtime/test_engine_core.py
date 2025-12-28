import pytest

import cascade as cs
from cascade.graph.build import build_graph
from cascade.runtime import Engine, MessageBus, ExecutionPlan
from cascade.testing import SpyExecutor, MockSolver


# --- Test Case ---


@pytest.mark.asyncio
async def test_engine_follows_solver_plan():
    # 1. Define a simple workflow (the graph structure doesn't matter much
    # as the MockSolver will override the plan)
    @cs.task
    def task_a():
        pass

    @cs.task
    def task_b(x):
        pass

    workflow = task_b(task_a())
    graph, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")

    # 2. Define the execution plan that the MockSolver will return
    # A simple sequential plan: [A], then [B]
    mock_plan: ExecutionPlan = [[node_a], [node_b]]

    # 3. Setup test doubles and Engine
    solver = MockSolver(plan=mock_plan)
    executor = SpyExecutor()
    bus = MessageBus()

    engine = Engine(solver=solver, executor=executor, bus=bus)

    # 4. Run the engine
    await engine.run(workflow)

    # 5. Assert the executor was called in the correct order
    assert len(executor.call_log) == 2
    assert executor.call_log[0].name == "task_a"
    assert executor.call_log[1].name == "task_b"
