from unittest.mock import MagicMock
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.system import SystemControlToken
from cascade.std.system.drainer import drain_signal


def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = drain_signal(inputs, MagicMock(), MagicMock())

    assert "out" in outputs
    output_payload = outputs["out"].payload

    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "DRAIN"
