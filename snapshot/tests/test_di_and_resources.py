import pytest
from unittest.mock import MagicMock
import cascade as cs

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
    connection.url = config['db_url']
    yield connection
    print("TEARDOWN: db_connection")
    connection.close()

# --- Test Tasks ---

@cs.task
def task_using_resource(conn = cs.inject("db_connection")):
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
    # Teardown order should be reverse of setup
    # TODO: We need a way to verify setup/teardown calls, maybe via events.

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
    engine.register(db_connection) # Register the original

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