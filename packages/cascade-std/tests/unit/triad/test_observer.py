import pytest
from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


@pytest.fixture
def event_queue() -> Queue:
    return Queue()


async def test_observer_processes_start_event(event_queue: Queue):
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event(event_queue: Queue):
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace(event_queue: Queue):
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
