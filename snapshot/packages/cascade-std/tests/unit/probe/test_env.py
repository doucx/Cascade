import os
from unittest.mock import MagicMock, patch
from cascade.spec.physical.nodes import Token
from cascade.std.probe.env import env_probe


def test_env_probe_samples_os_environ():
    inputs = {"name": Token(payload="TEST_VAR")}

    with patch.dict(os.environ, {"TEST_VAR": "cascade_value"}):
        outputs = env_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "cascade_value"


def test_env_probe_returns_none_if_env_missing():
    inputs = {"name": Token(payload="NON_EXISTENT_VAR")}

    # Ensure it's not in environ
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]

    outputs = env_probe(inputs, MagicMock(), MagicMock())
    assert outputs["out"].payload is None
