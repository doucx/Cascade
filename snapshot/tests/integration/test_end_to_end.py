import pytest
import asyncio
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.engine import Engine


@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.messaging_bus", mock_bus)
    return mock_bus


def test_e2e_linear_workflow(mock_messaging_bus):
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    result = asyncio.run(engine.run(final_greeting))

    assert result == "Hello, Cascade!"

    # Assertions are now on the INTENT (semantic ID), not the output!
    mock_messaging_bus.info.assert_any_call("run.started", targets="greet")
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
    mock_messaging_bus.info.assert_any_call("task.finished_success", task_name="get_name", duration=pytest.approx(0, abs=1))
    mock_messaging_bus.info.assert_any_call("task.started", task_name="greet")
    mock_messaging_bus.info.assert_any_call("run.finished_success", duration=pytest.approx(0, abs=1))
    
    # Check that it was not called with a failure message
    mock_messaging_bus.error.assert_not_called()


def test_e2e_failure_propagation(mock_messaging_bus):
    @cs.task
    def failing_task():
        raise ValueError("Something went wrong")

    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        asyncio.run(engine.run(failing_task()))

    # Assert that the correct failure messages were sent
    mock_messaging_bus.error.assert_any_call(
        "task.finished_failure",
        task_name="failing_task",
        duration=pytest.approx(0, abs=1),
        error="ValueError: Something went wrong"
    )
    mock_messaging_bus.error.assert_any_call(
        "run.finished_failure",
        duration=pytest.approx(0, abs=1),
        error=pytest.string_containing("ValueError: Something went wrong")
    )