from unittest.mock import patch

from cascade.spec.physics import Token
from cascade.vm.instructions.bleacher import standard_bleacher


def test_standard_bleacher_extracts_payloads():
    """
    Tests that the bleacher correctly extracts payloads from input tokens
    and assembles them into a kwargs dictionary for the worker.
    """
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }

    outputs = standard_bleacher(inputs)

    assert "worker_input" in outputs
    worker_token = outputs["worker_input"]
    assert isinstance(worker_token, Token)
    assert worker_token.payload == {"arg1": "hello", "arg2": 123}


def test_standard_bleacher_generates_trace_with_timestamp():
    """
    Tests that the bleacher captures a start timestamp and places it in a
    separate trace token.
    """
    MOCK_TIMESTAMP = 12345.6789
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({"data": Token(payload=1)})

    assert "trace_output" in outputs
    trace_token = outputs["trace_output"]
    assert isinstance(trace_token, Token)
    assert isinstance(trace_token.payload, dict)
    assert trace_token.payload.get("start_ts") == MOCK_TIMESTAMP


def test_standard_bleacher_with_empty_inputs():
    """
    Even with no inputs, the bleacher should produce a valid trace token
    and an empty kwargs payload for the worker.
    """
    MOCK_TIMESTAMP = 100.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({})

    assert "worker_input" in outputs
    assert outputs["worker_input"].payload == {}

    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {"start_ts": MOCK_TIMESTAMP}


def test_standard_bleacher_merges_traces():
    """
    Tests that the bleacher merges trace information from all input tokens
    before adding its own timestamp. The last-seen key should win on conflict.
    """
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher(inputs)

    assert "trace_output" in outputs
    trace_payload = outputs["trace_output"].payload

    # Check for merged data
    assert trace_payload.get("id") == "B"  # Last write wins on conflict
    assert trace_payload.get("source") == "X"
    assert trace_payload.get("retry") == 1

    # Check for new timestamp
    assert trace_payload.get("start_ts") == MOCK_TIMESTAMP
