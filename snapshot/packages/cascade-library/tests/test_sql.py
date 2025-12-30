import pytest
import cascade as cs
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Skip if sqlalchemy missing
pytest.importorskip("sqlalchemy")


@cs.resource
def sqlite_db():
    # Setup an in-memory SQLite database.
    # Because tasks now run in a separate thread pool, we must ensure:
    # 1. We share the same connection (StaticPool) so data persists across tasks.
    # 2. We disable thread checking (check_same_thread=False) so the connection created
    #    here can be used by the worker threads.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create a table
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Alice')"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Bob')"))
        conn.commit()

    yield engine

    engine.dispose()


@pytest.fixture
def db_engine():
    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    engine.register(sqlite_db)
    return engine


@pytest.mark.asyncio
async def test_sql_query_success(db_engine):
    # Define a workflow using the 'sqlite_db' resource via explicit injection
    users = cs.sql(
        "SELECT * FROM users ORDER BY name", conn=cs.inject("sqlite_db")
    )

    result = await db_engine.run(users)

    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_sql_with_params(db_engine):
    target = cs.sql(
        "SELECT * FROM users WHERE name = :name",
        conn=cs.inject("sqlite_db"),
        params={"name": "Bob"},
    )

    result = await db_engine.run(target)

    assert len(result) == 1
    assert result[0]["name"] == "Bob"


@pytest.mark.asyncio
async def test_sql_missing_resource():
    target = cs.sql("SELECT 1", conn=cs.inject("non_existent_db"))

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    # We don't register anything

    # With the new scanning logic, it should fail at setup time!
    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)


def test_sql_factory_returns_task_object():
    """
    Verify that cs.sql is now a Task object that supports composition.
    """
    assert hasattr(cs.sql, "map")
    assert hasattr(cs.sql, "with_retry")
    assert callable(cs.sql.map)