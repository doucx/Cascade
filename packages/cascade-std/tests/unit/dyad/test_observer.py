from unittest.mock import MagicMock

import pytest
from cascade.spec import EventIR, EventState, EventType
from cascade.spec.physical.nodes import Token
from cascade.std.system.observer import standard_observer


@pytest.fixture
def mock_bus() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_resources(mock_bus: MagicMock) -> MagicMock:
    registry = MagicMock()
    registry.get.return_value = mock_bus
    return registry


def test_observer_publishes_ir_to_bus(mock_bus: MagicMock, mock_resources: MagicMock):
    # 1. Prepare Input
    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {"rid": "run-1"},
        "phy": {"nid": "node-abc.stain"},
        "data": {"state": EventState.SUCCEEDED, "duration_ms": 100},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, MagicMock(), mock_resources)

    # 3. Assert
    # Assert that the observer requested the bus from resources
    mock_resources.get.assert_called_once_with("system.event_bus")

    # Assert that the observer published the IR payload to the bus
    mock_bus.publish_ir.assert_called_once_with(ir_payload)


def test_observer_handles_no_bus(mock_resources: MagicMock):
    # Set up resources to return None for the bus
    mock_resources.get.return_value = None

    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {},
        "phy": {"nid": "n1"},
        "data": {},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # Execute and expect no exceptions
    standard_observer(inputs, MagicMock(), mock_resources)

    # Bus's publish method should not have been called
    # (since bus itself is None, getattr would fail if not guarded)
    # The main test is that it doesn't crash.
