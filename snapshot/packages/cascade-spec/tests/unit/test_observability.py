import time
from cascade.spec import (
    EventIR,
    EventType,
    EventState,
    PhysicalAnchor,
    EventContext,
)


def test_event_type_enums():
    assert EventType.LIFECYCLE == "task.lifecycle"
    assert EventType.ERROR == "system.error"
    # Verify StrEnum behavior
    assert "task.lifecycle" == EventType.LIFECYCLE


def test_event_state_enums():
    assert EventState.RUNNING == "Running"
    assert EventState.FAILED == "Failed"


def test_event_ir_structure():
    # Verify we can instantiate a valid EventIR structure
    now = time.time()

    ctx: EventContext = {"rid": "run-123", "pid": "proj-abc"}
    phy: PhysicalAnchor = {"nid": "node-hash-xyz"}

    event: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now,
        "ctx": ctx,
        "phy": phy,
        "data": {"state": EventState.RUNNING, "inputs": {"a": 1}},
    }

    assert event["v"] == "1.0"
    assert event["t"] == "task.lifecycle"
    assert event["ctx"]["rid"] == "run-123"
    assert event["phy"]["nid"] == "node-hash-xyz"
    assert event["data"]["state"] == "Running"
