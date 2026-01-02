import pytest
from unittest.mock import patch, MagicMock

from cascade.spec.physics import Token
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.triad import StainNode
from cascade.vm.instructions.stainer import standard_stainer


def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    assert output_token.tag == "default"
    assert output_token.trace["id"] == "task_A"
    assert output_token.trace["start_ts"] == start_ts
    assert output_token.trace["end_ts"] == end_ts
    assert output_token.trace["duration"] == 2.5


def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    assert output_token.tag == "error"
    assert output_token.trace["end_ts"] == end_ts
    assert pytest.approx(output_token.trace["duration"]) == 0.1


def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node)

    output_token = outputs["output"]
    assert output_token.trace["duration"] == 0.0
    assert output_token.trace["end_ts"] == end_ts
