import pytest
from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


@pytest.fixture
def event_queue() -> Queue:
    return Queue()


@pytest.fixture
def mock_resources(event_queue: Queue) -> MagicMock:
    registry = MagicMock()
    registry.get.return_value = event_queue
    return registry


async def test_observer_processes_start_event(
    event_queue: Queue, mock_resources: MagicMock
):
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event(
    event_queue: Queue, mock_resources: MagicMock
):
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", trace=end_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace(event_queue: Queue, mock_resources: MagicMock):
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
