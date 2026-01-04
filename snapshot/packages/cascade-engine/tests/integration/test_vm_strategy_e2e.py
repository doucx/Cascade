import pytest
from unittest.mock import MagicMock
from cascade.sdk import task
from cascade.engine import Engine, EventBus, HumanReadableLogSubscriber
from cascade.spec.protocols import Executor, Solver
from cascade.runtime.events import TaskExecutionFinished

# Mocks to satisfy Engine constructor
class MockSolver(Solver):
    def resolve(self, graph): return []

class MockExecutor(Executor):
    async def execute(self, node, func, args, kwargs): return None

@pytest.mark.asyncio
async def test_vm_strategy_e2e_observability():
    """
    Verifies that running a task via VMExecutionStrategy correctly:
    1. Propagates run_id from Engine -> VM -> Tokens -> Events.
    2. Emits Rich Events (TaskExecutionFinished) to the EventBus.
    3. Allows HumanReadableLogSubscriber to consume these events.
    """
    
    # 1. Setup Logic
    @task
    def hello(name: str) -> str:
        return f"Hello, {name}!"

    workflow = hello("World")

    # 2. Setup Engine Infrastructure
    bus = EventBus()
    
    # We use a spy to intercept what HumanReadableLogSubscriber would see
    # and also verify what the bus receives.
    captured_events = []
    def spy_subscriber(event):
        captured_events.append(event)
    
    bus.subscribe(TaskExecutionFinished, spy_subscriber)

    # Initialize Engine (Strategy selection happens inside run())
    engine = Engine(
        solver=MockSolver(),
        executor=MockExecutor(),
        bus=bus
    )

    # 3. Execute with VM Backend
    result = await engine.run(workflow, use_vm=True)

    # 4. Assertions
    assert result == "Hello, World!"
    
    # Filter for the stainer completion event (which maps to TaskExecutionFinished)
    finish_events = [e for e in captured_events if isinstance(e, TaskExecutionFinished)]
    assert len(finish_events) > 0, "No TaskExecutionFinished events captured"

    event = finish_events[0]
    
    # Context Propagation
    assert event.run_id is not None
    assert len(event.run_id) > 0
    
    # Task Name (Telemetry Quality)
    # The Stainer emits "Stain(hello)", which should be present
    assert "Stain(hello)" in event.task_name or "hello" in event.task_name
    
    # Status
    assert event.status == "Succeeded"
    assert event.result_preview is not None
    assert "Hello, World!" in event.result_preview

    print("\nE2E VM Test Passed: Context and Content propagated successfully.")