import io
import json
import pytest
from cascade.runtime.renderers import CliRenderer, JsonRenderer
from cascade.common.messaging import MessageStore


@pytest.fixture
def msg_store():
    store = MessageStore()
    # Manually add a message for testing
    store._messages["test.hello"] = "Hello, {name}!"
    return store


def test_cli_renderer(msg_store):
    output = io.StringIO()
    renderer = CliRenderer(store=msg_store, stream=output)

    renderer.render("test.hello", "info", name="World")

    assert "Hello, World!" in output.getvalue()


def test_json_renderer_structure_and_content():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output)

    renderer.render("user.created", "info", user_id=123, status="active")

    log_line = output.getvalue()
    data = json.loads(log_line)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["event_id"] == "user.created"
    assert data["data"]["user_id"] == 123
    assert data["data"]["status"] == "active"


def test_json_renderer_log_level_filtering():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output, min_level="WARNING")

    # This should be rendered
    renderer.render("api.error", "error", code=500)
    # This should be filtered out
    renderer.render("request.start", "info", path="/")

    logs = output.getvalue().strip()
    assert '"level": "ERROR"' in logs
    assert '"level": "INFO"' not in logs
    # Ensure it's a single line of JSON
    assert len(logs.splitlines()) == 1
