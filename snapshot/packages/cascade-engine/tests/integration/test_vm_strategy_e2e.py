import pytest
from unittest.mock import MagicMock
from cascade.spec.task import task
from cascade.engine import Engine
from cascade.runtime.event_bus import EventBus
from cascade.runtime.events import TaskExecutionFinished, RunStarted
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@task
def hello_task(name: str) -> str:
    return f"Hello, {name}!"


@pytest.mark.asyncio
async def test_vm_strategy_e2e_observability():
    """
    Verifies that running a task via the VM strategy:
    1. Executes correctly.
    2. Emits LifeCycle events (Started, Finished).
    3. Events contain the correct run_id (Context Injection works).
    """
    # 1. Setup Engine components
    bus = EventBus()
    executor = LocalExecutor()
    solver = NativeSolver()
    engine = Engine(solver=solver, executor=executor, bus=bus)

    # 2. Setup Event Spy
    captured_events = []
    bus.subscribe(TaskExecutionFinished, captured_events.append)
    bus.subscribe(RunStarted, captured_events.append)

    # 3. Execute Workflow using VM Strategy
    flow = hello_task("World")
    result = await engine.run(flow, use_vm=True)

    # 4. Verify Result
    assert result == "Hello, World!"

    # 5. Verify Observability
    # Check that we got a RunStarted event
    run_started = next((e for e in captured_events if isinstance(e, RunStarted)), None)
    assert run_started is not None
    run_id = run_started.run_id
    assert run_id is not None

    # Check that we got a TaskExecutionFinished event with the SAME run_id
    task_finished = next((e for e in captured_events if isinstance(e, TaskExecutionFinished)), None)
    assert task_finished is not None
    
    assert task_finished.task_name == "hello_task"
    assert task_finished.status == "Succeeded"
    
    # THE CRITICAL CHECK: Did the run_id propagate from Engine -> VM -> Token -> EventIR -> Bus -> Event?
    assert task_finished.run_id == run_id, \
        f"Context Injection Failed: Expected run_id {run_id}, got {task_finished.run_id}"

    print(f"E2E Verification Passed. Run ID: {run_id}")