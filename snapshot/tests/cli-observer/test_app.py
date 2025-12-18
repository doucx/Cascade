import pytest
from unittest.mock import MagicMock, AsyncMock

# The module we are testing
from cascade.cli.observer import app as observer_app

# The objects we need to mock
# We will patch 'bus' and 'MqttConnector' where they are USED.


@pytest.fixture
def mock_messaging_bus(monkeypatch) -> MagicMock:
    """Mocks the global message bus used by the observer app."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.cli.observer.app.bus", mock_bus)
    return mock_bus


@pytest.fixture
def mock_connector(monkeypatch) -> AsyncMock:
    """Mocks the MqttConnector class to prevent network calls."""
    mock_instance = AsyncMock()
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cascade.cli.observer.app.MqttConnector", mock_class)
    return mock_instance


# --- Test Cases ---

@pytest.mark.asyncio
async def test_on_message_handles_task_running_event(mock_messaging_bus):
    """
    Verify that a 'RUNNING' TaskStateEvent is correctly parsed and rendered.
    """
    # Arrange: A sample telemetry payload
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "RUNNING",
            "task_name": "process_data",
        },
    }

    # Act: Directly call the callback function
    await observer_app.on_message("a/topic", payload)

    # Assert: Verify the bus was called with the correct semantic intent
    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.RUNNING",
        task_name="process_data",
        duration_ms=0,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_completed_event(mock_messaging_bus):
    """
    Verify that a 'COMPLETED' TaskStateEvent is correctly parsed.
    """
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "COMPLETED",
            "task_name": "generate_report",
            "duration_ms": 123.45,
        },
    }

    await observer_app.on_message("a/topic", payload)

    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.COMPLETED",
        task_name="generate_report",
        duration_ms=123.45,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_failed_event(mock_messaging_bus):
    """
    Verify that a 'FAILED' TaskStateEvent is correctly parsed.
    """
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "FAILED",
            "task_name": "api_call",
            "duration_ms": 50.0,
            "error": "TimeoutError",
        },
    }

    await observer_app.on_message("a/topic", payload)

    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.FAILED",
        task_name="api_call",
        duration_ms=50.0,
        error="TimeoutError",
    )


@pytest.mark.asyncio
async def test_on_message_prints_run_header_only_once(mock_messaging_bus):
    """
    Verify that the run header is printed only for the first message of a new run.
    """
    payload1 = {
        "header": {"run_id": "run-abc"},
        "body": {"type": "LifecycleEvent", "event": "ENGINE_STARTED"},
    }
    payload2 = {
        "header": {"run_id": "run-abc"},
        "body": {"type": "TaskStateEvent", "state": "RUNNING", "task_name": "task1"},
    }
    
    # Reset the global tracker for a clean test run
    observer_app.seen_run_ids.clear()

    # Act
    await observer_app.on_message("a/topic", payload1)
    await observer_app.on_message("a/topic", payload2)

    # Assert
    # Check that the header was printed exactly once
    header_call = mock_messaging_bus.info.call_args_list[0]
    assert header_call.args[0] == "observer.telemetry.run_header"
    assert header_call.kwargs["run_id"] == "run-abc"
    
    # Check that subsequent calls did not print the header again
    assert len(mock_messaging_bus.info.call_args_list) == 3 # Header, Started, Running
    assert all(
        call.args[0] != "observer.telemetry.run_header"
        for call in mock_messaging_bus.info.call_args_list[1:]
    )