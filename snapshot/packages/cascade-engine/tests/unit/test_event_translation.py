import time
from cascade.spec import EventIR, EventType, EventState
from cascade.runtime.events import (
    Event, 
    TaskExecutionStarted, 
    TaskExecutionFinished, 
    TaskSkipped
)

def test_hydrate_lifecycle_started():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.RUNNING,
            "task_id": "logical-task-1",
            "task_name": "MyTask"
        }
    }
    
    # Verify the dynamically bound method exists and works
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionStarted)
    assert event.run_id == "run-xyz"
    assert event.timestamp == ts
    assert event.task_id == "logical-task-1"
    assert event.task_name == "MyTask"

def test_hydrate_lifecycle_finished_success():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.SUCCEEDED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "duration_ms": 1500.0,
            "result_preview": "42"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionFinished)
    assert event.status == "Succeeded"
    assert event.duration == 1.5  # Verified ms -> s conversion
    assert event.result_preview == "42"
    assert event.error is None

def test_hydrate_lifecycle_finished_failed():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.FAILED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "duration_ms": 100.0,
            "error": "ValueError: boom"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskExecutionFinished)
    assert event.status == "Failed"
    assert event.error == "ValueError: boom"

def test_hydrate_lifecycle_skipped():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": ts,
        "ctx": {"rid": "run-xyz"},
        "phy": {"nid": "node-123"},
        "data": {
            "state": EventState.SKIPPED,
            "task_id": "logical-task-1",
            "task_name": "MyTask",
            "reason": "ConditionFalse"
        }
    }
    
    event = Event.from_ir(ir)
    
    assert isinstance(event, TaskSkipped)
    assert event.reason == "ConditionFalse"

def test_hydrate_unknown_type():
    ts = time.time()
    ir: EventIR = {
        "v": "1.0",
        "t": "unknown.type", # type: ignore
        "ts": ts,
        "ctx": {},
        "phy": {"nid": "n1"},
        "data": {}
    }
    
    event = Event.from_ir(ir)
    
    # Should fallback to base Event
    assert type(event) is Event
    assert event.timestamp == ts