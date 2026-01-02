from unittest.mock import patch, MagicMock

from cascade.spec.physics import Token
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.triad import BleachNode
from cascade.vm.instructions.bleacher import standard_bleacher


def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node


def test_standard_bleacher_extracts_payloads():
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_bleach_node(
        {"arg1": PortRole.DATA, "arg2": PortRole.DATA}
    )

    outputs = standard_bleacher(inputs, node)

    assert "worker_input" in outputs
    worker_token = outputs["worker_input"]
    assert isinstance(worker_token, Token)
    assert worker_token.payload == {"arg1": "hello", "arg2": 123}


def test_standard_bleacher_generates_trace_with_timestamp():
    MOCK_TIMESTAMP = 12345.6789
    node = create_mock_bleach_node({"data": PortRole.DATA})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({"data": Token(payload=1)}, node)

    assert "trace_output" in outputs
    trace_token = outputs["trace_output"]
    assert isinstance(trace_token, Token)
    assert isinstance(trace_token.payload, dict)
    assert trace_token.payload.get("start_ts") == MOCK_TIMESTAMP


def test_standard_bleacher_with_empty_inputs():
    MOCK_TIMESTAMP = 100.0
    node = create_mock_bleach_node({})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({}, node)

    assert "worker_input" in outputs
    assert outputs["worker_input"].payload == {}

    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {"start_ts": MOCK_TIMESTAMP}


def test_standard_bleacher_merges_traces():
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }
    node = create_mock_bleach_node(
        {"token_a": PortRole.DATA, "token_b": PortRole.DATA}
    )

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher(inputs, node)

    assert "trace_output" in outputs
    trace_payload = outputs["trace_output"].payload

    # Check for merged data
    assert trace_payload.get("id") == "B"  # Last write wins on conflict
    assert trace_payload.get("source") == "X"
    assert trace_payload.get("retry") == 1

    # Check for new timestamp
    assert trace_payload.get("start_ts") == MOCK_TIMESTAMP
