import pytest
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.services.observability.events import (
    ResourceAcquired,
    ResourceReleased,
    Event,
)
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver

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


def test_di_end_to_end():
    import asyncio

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    engine.register(config)
    engine.register(db_connection)

    result = asyncio.run(engine.run(task_using_resource()))

    assert result == "production_url"


def test_resource_events():
    import asyncio

    events = []
    bus = cs.EventBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    engine.register(config)
    engine.register(db_connection)

    asyncio.run(engine.run(task_using_resource()))

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
    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        m = MagicMock()
        m.url = "mock_db_url"
        yield m
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    engine.register(config)
    engine.register(db_connection)  # Register the original

    import asyncio

    # Override the db_connection resource using the container's robust method
    with engine.resource_container.override("db_connection", mock_db_connection):
        result = asyncio.run(engine.run(task_using_resource()))

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored.
    # We create a NEW engine to ensure a clean state and avoid cache pollution from the previous run.
    # This is the most robust way to test restoration.
    engine_after = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    engine_after.register(config)
    engine_after.register(db_connection)

    result_after = asyncio.run(engine_after.run(task_using_resource()))
    assert result_after == "production_url"


def test_resource_must_be_generator():
    with pytest.raises(TypeError, match="must be a generator"):

        @cs.resource
        def not_a_generator():
            return "foo"


def test_unregistered_resource_raises_error():
    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    # Note: We do NOT register any resources.

    @cs.task
    def task_needs_unregistered(conn=cs.inject("non_existent_db")):
        pass

    with pytest.raises(
        NameError, match="Resource 'non_existent_db' is required but not registered"
    ):
        import asyncio

        asyncio.run(engine.run(task_needs_unregistered()))


def test_resource_scan_finds_inject_in_dict():
    from cascade.runtime.services.resources.container import ResourceContainer
    from cascade.execution.graph.model.build import build_graph

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
