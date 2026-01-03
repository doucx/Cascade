from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.terminator import halt_signal


async def test_halt_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await halt_signal(inputs, MagicMock())

    assert "out" in outputs
    output_payload = outputs["out"].payload

    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "HALT"
