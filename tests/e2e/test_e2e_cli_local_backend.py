import pytest
from typer.testing import CliRunner
from pathlib import Path

# Apps to test
from cascade.cli.controller.app import app as controller_app
from cascade.cli.observer.app import app as observer_app
from cascade.connectors.local import LocalConnector


from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer


@pytest.fixture
def isolated_db_path(tmp_path: Path, monkeypatch):
    """
    Fixture to create an isolated SQLite database for tests and patch the
    hardcoded default path in the CLI applications.
    """
    # CRITICAL: Reset the global message bus renderer before each test run.
    # This prevents state pollution where the bus holds a renderer pointing to
    # a closed stream from a previous CliRunner context.
    bus.set_renderer(CliRenderer(store=bus.store))
    db_path = tmp_path / "test-control.db"

    # Patch 1: The default path in the LocalConnector constructor, used by cs-controller
    # We patch the class itself to replace the default __init__ behavior.
    original_init = LocalConnector.__init__

    def patched_init(self, db_path=str(db_path), **kwargs):
        # We force our test db_path, ignoring whatever might be passed.
        original_init(self, db_path=str(db_path), **kwargs)

    monkeypatch.setattr(
        "cascade.cli.controller.app.LocalConnector",
        lambda *args, **kwargs: LocalConnector(db_path=str(db_path)),
    )

    # Patch 2: The hardcoded path in cs-observer's status command logic.
    monkeypatch.setattr(
        "cascade.cli.observer.app.Path.expanduser", lambda self: db_path
    )

    return db_path


def test_set_and_status_local(isolated_db_path: Path):
    """
    Verify that `controller set-limit` creates a db entry and `observer status` can read it.
    """
    runner = CliRunner()

    # 1. Set a constraint using the sqlite backend
    result_set = runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "10/s", "--backend", "local"],
    )
    assert result_set.exit_code == 0
    assert isolated_db_path.exists()

    # 2. Check the status
    result_status = runner.invoke(observer_app, ["status", "--backend", "local"])
    assert result_status.exit_code == 0
    assert "global" in result_status.stderr
    assert "rate_limit" in result_status.stderr
    assert "{'rate': '10/s'}" in result_status.stderr


def test_resume_local(isolated_db_path: Path):
    """
    Verify that `controller resume` correctly deletes a constraint from the database.
    """
    runner = CliRunner()

    # 1. Set a constraint
    runner.invoke(
        controller_app,
        [
            "set-limit",
            "--scope",
            "task:api",
            "--concurrency",
            "5",
            "--backend",
            "local",
        ],
    )
    assert isolated_db_path.exists()

    # 2. Resume the scope
    result_resume = runner.invoke(
        controller_app, ["resume", "task:api", "--backend", "local"]
    )
    assert result_resume.exit_code == 0

    # 3. Check the status and verify it's gone
    result_status = runner.invoke(observer_app, ["status", "--backend", "local"])
    assert result_status.exit_code == 0
    assert "No active constraints found" in result_status.stderr
    assert "task:api" not in result_status.stderr


def test_mqtt_backend_leaves_no_trace(isolated_db_path: Path, monkeypatch):
    """
    Verify that running commands with `--backend mqtt` does not interact with the SQLite DB.
    """
    # We need to mock the MqttConnector to avoid network errors
    monkeypatch.setattr(
        "cascade.cli.controller.app.MqttConnector", lambda *a, **kw: None
    )

    runner = CliRunner()
    runner.invoke(
        controller_app,
        ["set-limit", "--scope", "global", "--rate", "1/s", "--backend", "mqtt"],
    )

    # Even though the command "fails" without a mock, it shouldn't touch the filesystem.
    # The important check is that the db file was NOT created.
    assert not isolated_db_path.exists()
