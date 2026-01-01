from queue import Queue

from cascade.spec.physics import Token
from cascade.vm.instructions.observer import standard_observer, ObservedEvent


def test_observer_processes_start_event():
    """
    Tests that a token containing only start information (from a Bleacher)
    is correctly processed as a 'start' event.
    """
    # 1. Setup
    queue = Queue()
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


def test_observer_processes_end_event():
    """
    Tests that a token containing end information (from a Stainer)
    is correctly processed as an 'end' event.
    """
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
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


def test_observer_with_empty_trace():
    """
    An empty trace should be treated as a 'start' event by default.
    """
    # 1. Setup
    queue = Queue()
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
