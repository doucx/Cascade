from unittest.mock import MagicMock, patch
from cascade.spec.physics import Token
from cascade.std.probe.context import param_probe


async def test_param_probe_lookups_value():
    inputs = {"name": Token(payload="db_url"), "trigger": Token(payload=None)}

    # Mock WorkflowContext
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = "sqlite:///:memory:"

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock())

    assert outputs["out"].payload == "sqlite:///:memory:"
    mock_ctx.get_value.assert_called_once_with("db_url")


async def test_param_probe_returns_none_if_missing():
    inputs = {"name": Token(payload="missing"), "trigger": Token(payload=None)}
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = None

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock())

    assert outputs["out"].payload is None