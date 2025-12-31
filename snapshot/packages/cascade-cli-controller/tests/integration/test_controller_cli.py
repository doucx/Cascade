import pytest
from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock

from cascade.cli.controller.app import app

runner = CliRunner()


@pytest.fixture
def mock_publish_pause():
    with patch(
        "cascade.cli.controller.app._publish_pause", new_callable=AsyncMock
    ) as mock:
        yield mock


def test_pause_command_dispatches_correctly(mock_publish_pause):
    # Act: Simulate command line invocation
    result = runner.invoke(app, ["pause", "task:my-task", "--ttl", "300"])

    # Assert: The command executed successfully and called our logic function
    assert result.exit_code == 0
    mock_publish_pause.assert_called_once()

    # Assert that arguments were parsed and passed correctly
    call_args = mock_publish_pause.call_args
    assert call_args.kwargs["scope"] == "task:my-task"
    assert call_args.kwargs["ttl"] == 300
    assert call_args.kwargs["hostname"] == "localhost"  # Verifies default value
