import pytest
import cascade as cs
from cascade.runtime import Engine, EventBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.testing import SpySubscriber


@pytest.mark.asyncio
async def test_vm_telemetry_e2e():
    """
    Verifies that running a workflow with the VM strategy produces
    correct telemetry events (Started/Finished) with populated
    task_name and run_id.
    """
    
    # 1. Define Workflow
    @cs.task(name="MyCalcTask")
    def calc(x: int) -> int:
        return x * 2

    # Using a condition to ensure the new VM traversal logic is also exercised
    @cs.task(name="MyCondition")
    def should_run() -> bool:
        return True

    workflow = calc(21).run_if(should_run())

    # 2. Setup Engine with VM
    bus = EventBus()
    spy = SpySubscriber(bus)
    
    engine = Engine(
        solver=NativeSolver(), 
        executor=LocalExecutor(), 
        bus=bus
    )

    # 3. Run
    # Force use_vm=True to test the VM strategy
    result = await engine.run(workflow, use_vm=True)
    assert result == 42

    # 4. Assert Telemetry
    
    # A. Check Start Events
    started = spy.events_of_type(TaskExecutionStarted)
    task_names = sorted([e.task_name for e in started])
    # Note: 'calc' node and 'should_run' node.
    # The names come from @cs.task(name=...).
    assert "MyCalcTask" in task_names
    assert "MyCondition" in task_names
    
    # Check Run ID presence
    run_id = started[0].run_id
    assert run_id is not None
    assert all(e.run_id == run_id for e in started)

    # B. Check Finish Events
    finished = spy.events_of_type(TaskExecutionFinished)
    finished_map = {e.task_name: e for e in finished}
    
    assert "MyCalcTask" in finished_map
    calc_event = finished_map["MyCalcTask"]
    
    assert calc_event.status == "Succeeded"
    assert calc_event.duration >= 0.0
    assert calc_event.run_id == run_id
    
    print("VM Telemetry E2E Passed: Context and Metadata verified.")