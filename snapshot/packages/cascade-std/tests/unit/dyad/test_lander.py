from unittest.mock import MagicMock, patch

from cascade.spec.physical.dyad import LanderNode
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.specs.dyad import LanderSpec
from cascade.std.dyad.lander import standard_lander


def create_mock_lander_node(output_ports_config):
    node = MagicMock(spec=LanderNode)
    node.id = "test_node.land"
    node.name = "Land(test_node)"
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


def test_standard_lander_success_path():
    # Setup Inputs (Result from ComputeService)
    start_ts = 1000.0
    end_ts = 1005.0
    result_payload = "ExecutionResult"

    inputs = {
        LanderSpec.result_token.name: Token(
            payload=result_payload, trace={"start_ts": start_ts, "rid": "run-1"}
        )
    }

    node = create_mock_lander_node(
        {"output_default": PortRole.DATA, "output_error": PortRole.DATA}
    )

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_lander(inputs, node, MagicMock())

    # Verify Outputs
    assert "output_default" in outputs
    assert "output_error" not in outputs

    out_token = outputs["output_default"]
    assert out_token.payload == result_payload
    assert out_token.trace["duration"] == 5.0
    assert out_token.trace["rid"] == "run-1"


def test_standard_lander_error_path():
    error = ValueError("Task Failed")
    inputs = {
        LanderSpec.result_token.name: Token(payload=error, trace={"start_ts": 1000.0})
    }

    node = create_mock_lander_node(
        {"output_default": PortRole.DATA, "output_error": PortRole.DATA}
    )

    outputs = standard_lander(inputs, node, MagicMock())

    assert "output_error" in outputs
    assert "output_default" not in outputs
    assert outputs["output_error"].payload == error
