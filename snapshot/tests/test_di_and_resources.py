import pytest
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event

# --- Test Resources ---


@cs.resource
def config():
    """A simple resource that provides a config dict."""
    print("SETUP: config")
    yield {"db_url": "production_url"}
    print("TEARDOWN: config")


@cs.resource
def db_connection(config: dict = cs.inject("config")):
    """A resource that depends on another resource."""
    print(f"SETUP: db_connection using {config['db_url']}")
    connection = MagicMock()
    connection.url = config["db_url"]
    yield connection
    print("TEARDOWN: db_connection")
    connection.close()


# --- Test Tasks ---


@cs.task
def task_using_resource(conn=cs.inject("db_connection")):
    """A task that injects a resource."""
    assert isinstance(conn, MagicMock)
    return conn.url


# --- Test Cases ---


def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)

    result = engine.run(task_using_resource())

    assert result == "production_url"


def test_resource_events():
    """Tests that resource lifecycle events are emitted."""
    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(bus=bus)
    engine.register(config)
    engine.register(db_connection)

    engine.run(task_using_resource())

    # Check for ResourceAcquired events
    acquired_names = [
        e.resource_name for e in events if isinstance(e, ResourceAcquired)
    ]
    # 'config' must be acquired before 'db_connection' because db_connection depends on config
    assert "config" in acquired_names
    assert "db_connection" in acquired_names
    assert acquired_names.index("config") < acquired_names.index("db_connection")

    # Check for ResourceReleased events
    released_names = [
        e.resource_name for e in events if isinstance(e, ResourceReleased)
    ]
    # Teardown is in reverse order (LIFO via ExitStack)
    assert "db_connection" in released_names
    assert "config" in released_names
    assert released_names.index("db_connection") < released_names.index("config")


def test_resource_override():
    """Tests that a resource can be overridden for testing."""

    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        m = MagicMock()
        m.url = "mock_db_url"
        yield m
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)  # Register the original

    # Override the db_connection resource
    with cs.override_resource(engine, "db_connection", mock_db_connection):
        result = engine.run(task_using_resource())

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored
    result_after = engine.run(task_using_resource())
    assert result_after == "production_url"


def test_resource_must_be_generator():
    """Tests that a non-generator function cannot be a resource."""
    with pytest.raises(TypeError, match="must be a generator"):

        @cs.resource
        def not_a_generator():
            return "foo"
