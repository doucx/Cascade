from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


async def test_observer_processes_start_event():
    # 1. Setup
    queue = Queue()
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event():
    # 1. Setup
    queue = Queue()
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace():
    # 1. Setup
    queue = Queue()
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
