from unittest.mock import MagicMock

import cascade.sdk as cs
import pytest
from cascade.bus.events import (
    ResourceAcquired,
    ResourceReleased,
)

# --- Test Resources ---


@cs.resource
def config():
    print("SETUP: config")
    yield {"db_url": "production_url"}
    print("TEARDOWN: config")


@cs.resource
def db_connection(config: dict = cs.inject("config")):
    print(f"SETUP: db_connection using {config['db_url']}")
    connection = MagicMock()
    connection.url = config["db_url"]
    yield connection
    print("TEARDOWN: db_connection")
    connection.close()


# --- Test Tasks ---


@cs.task
def task_using_resource(conn=cs.inject("db_connection")):
    assert isinstance(conn, MagicMock)
    return conn.url


# --- Test Cases ---


@pytest.mark.asyncio
async def test_di_end_to_end(engine_factory):
    engine = engine_factory()
    engine.register(config)
    engine.register(db_connection)

    result = await engine.run(task_using_resource())

    assert result == "production_url"


@pytest.mark.asyncio
async def test_resource_events(engine_factory, bus_and_spy):
    bus, spy = bus_and_spy

    engine = engine_factory(bus=bus)
    engine.register(config)
    engine.register(db_connection)

    await engine.run(task_using_resource())

    # Check for ResourceAcquired events
    acquired_names = [
        e.resource_name for e in spy.events if isinstance(e, ResourceAcquired)
    ]
    # 'config' must be acquired before 'db_connection' because db_connection depends on config
    assert "config" in acquired_names
    assert "db_connection" in acquired_names
    assert acquired_names.index("config") < acquired_names.index("db_connection")

    # Check for ResourceReleased events
    released_names = [
        e.resource_name for e in spy.events if isinstance(e, ResourceReleased)
    ]
    # Teardown is in reverse order (LIFO via ExitStack)
    assert "db_connection" in released_names
    assert "config" in released_names
    assert released_names.index("db_connection") < released_names.index("config")


@pytest.mark.asyncio
async def test_resource_override(engine_factory):
    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        m = MagicMock()
        m.url = "mock_db_url"
        yield m
        print("TEARDOWN: mock_db_connection")

    engine = engine_factory()
    engine.register(config)
    engine.register(db_connection)  # Register the original

    # Override the db_connection resource using the container's robust method
    with engine.resource_container.override("db_connection", mock_db_connection):
        result = await engine.run(task_using_resource())

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored.
    # We create a NEW engine to ensure a clean state and avoid cache pollution from the previous run.
    engine_after = engine_factory()
    engine_after.register(config)
    engine_after.register(db_connection)

    result_after = await engine_after.run(task_using_resource())
    assert result_after == "production_url"


def test_resource_must_be_generator():
    with pytest.raises(TypeError, match="must be a generator"):

        @cs.resource
        def not_a_generator():
            return "foo"


@pytest.mark.asyncio
async def test_unregistered_resource_raises_error(engine):
    # Note: We do NOT register any resources.

    @cs.task
    def task_needs_unregistered(conn=cs.inject("non_existent_db")):
        pass

    with pytest.raises(
        NameError, match="Resource 'non_existent_db' is required but not registered"
    ):
        await engine.run(task_needs_unregistered())


def test_resource_scan_finds_inject_in_dict():
    from cascade.execution.graph.model.build import build_graph
    from cascade.runtime.services.resources.container import ResourceContainer

    @cs.resource
    def my_res():
        yield "foo"

    @cs.task
    def task_with_dict_inject(config: dict):
        pass

    # The Inject object is nested inside a dict
    flow = task_with_dict_inject(config={"db": cs.inject("my_res")})
    graph, _, executable_registry = build_graph(flow)

    container = ResourceContainer(bus=cs.EventBus())
    required = container.scan(graph, executable_registry)

    assert "my_res" in required
