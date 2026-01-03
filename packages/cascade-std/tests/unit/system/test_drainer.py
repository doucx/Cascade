from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.drainer import drain_signal


async def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await drain_signal(inputs, MagicMock())

    assert "out" in outputs
    output_payload = outputs["out"].payload

    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "DRAIN"
