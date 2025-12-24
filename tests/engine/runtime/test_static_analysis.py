import pytest
from unittest.mock import MagicMock

import cascade as cs
from cascade.runtime import Engine, HumanReadableLogSubscriber, MessageBus
from cascade.adapters.solvers import NativeSolver
from cascade.adapters.executors import LocalExecutor


@pytest.mark.asyncio
async def test_dynamic_recursion_emits_warning(monkeypatch):
    """
    Verifies that the engine emits a static analysis warning when it detects
    the dynamic recursion anti-pattern.
    """
    # 1. Mock the user-facing message bus that the subscriber uses
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)

    # 2. Define the anti-pattern
    @cs.task
    def some_other_task(x):
        return x  # A simple task

    @cs.task
    def dynamic_recursive_task(x):
        if x <= 0:
            return "done"
        # ANTI-PATTERN: Recursive call with another task call in its arguments
        return dynamic_recursive_task(some_other_task(x - 1))

    # 3. Setup a real engine and subscriber
    engine_event_bus = MessageBus()
    # The subscriber listens to the engine's events
    _ = HumanReadableLogSubscriber(engine_event_bus)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=engine_event_bus,  # Engine uses its internal event bus
    )

    # 4. Run the workflow
    await engine.run(dynamic_recursive_task(1))

    # 5. Assert the INTENT on the mocked user-facing bus
    mock_bus.warning.assert_called_once_with(
        "graph.analysis.warning",
        task_name="dynamic_recursive_task",
        warning_code="CS-W001",
        message=(
            "Task 'dynamic_recursive_task' uses a dynamic recursion pattern (calling other "
            "tasks in its arguments) which disables TCO optimizations, "
            "leading to significant performance degradation."
        ),
    )
