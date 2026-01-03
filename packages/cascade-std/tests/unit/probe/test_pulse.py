from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.probe.pulse import pulse_generator


async def test_pulse_generator_passes_token_forward():
    trace = {"origin": "pulse_test"}
    inputs = {"trigger": Token(payload="BOOM", trace=trace)}

    outputs = await pulse_generator(inputs, MagicMock())

    assert outputs["out"].payload == "BOOM"
    assert outputs["out"].trace["origin"] == "pulse_test"
