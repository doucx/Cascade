好的，问题很清楚。在我上一轮的修复中，我只关注了 `cascade-runtime` 内部的测试，而忽略了 `cascade-library` 中同样存在的大量本地 `engine` fixture 和手动 `Engine` 实例化。这些都成为了新的 `TypeError` 来源。

你的指令“全部改成全局的”是完全正确的，这正是我们实施依赖注入和 fixture 架构的最终目标：**在整个测试套件中，以统一、可维护的方式创建核心组件**。

我将执行一个全面的清理计划。

## [WIP] fix(tests): Unify all Engine instantiations in cascade-library tests to use global fixtures

### 错误分析

在 `packages/cascade-library/tests/integration/` 目录下的多个测试文件（如 `test_signal_provider.py`, `test_sql.py`, `test_stdio.py`, `test_time_provider.py`）中，存在着本地定义的 `engine` fixture 或直接在测试函数中手动调用 `cs.Engine(...)` 的情况。这些调用都没有更新以适应 `Engine` 新的、需要依赖注入的构造函数签名，从而导致了大量的 `TypeError`。

### 用户需求

修复 `cascade-library` 下所有集成测试中因 `Engine` 构造函数变更而导致的 `TypeError`，并将它们全部迁移至使用根 `conftest.py` 中定义的全局 `engine` fixture。

### 评论

这次修复是之前架构重构的最后一公里。通过将 `cascade-library` 的测试完全对齐到新的 fixture 体系，我们不仅解决了错误，还极大地提升了测试代码的一致性和简洁性。移除所有本地的 `Engine` 组装逻辑，让测试代码只关注业务逻辑本身，这是 fixture 模式带来的最大好处。

### 目标

1.  遍历所有报错的测试文件。
2.  删除所有本地定义的 `engine` 或 `db_engine` fixture。
3.  移除测试文件中所有对 `cs.Engine`, `NativeSolver`, `LocalExecutor` 的手动实例化和导入。
4.  修改所有测试函数的签名，使其直接接收全局的 `engine` fixture。

### 基本原理

我们将利用 Pytest fixture 的覆盖和发现机制。根目录的 `conftest.py` 中定义的 `engine` fixture 对所有子目录的测试都是可用的。我们只需在每个需要引擎的测试函数签名中加入 `engine` 参数，Pytest 就会自动为该测试注入一个正确配置的 `Engine` 实例。对于像 `test_sql.py` 这样需要额外资源（`sqlite_db`）的测试，我们将创建一个新的 fixture，它依赖于全局 `engine`，然后在其上注册所需的资源。

### 标签

#intent/fix #flow/ready #priority/critical #comp/library #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/test-fixtures #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `test_signal_provider.py`

删除本地 `engine` fixture，改为使用全局 fixture。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_signal_provider.py
~~~~~
~~~~~python.old
from cascade.runtime import Engine, EventBus
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.connectors.local import LocalBusConnector


@pytest.fixture
def local_connector():
    return LocalBusConnector()


@pytest.fixture
def engine(local_connector):
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
        connector=local_connector,
    )
~~~~~
~~~~~python.new
from cascade.connectors.local import LocalBusConnector


@pytest.fixture
def local_connector():
    return LocalBusConnector()


@pytest.fixture
def engine(engine_factory, local_connector):
    return engine_factory(
        connector=local_connector,
    )
~~~~~

#### Acts 2: 修复 `test_sql.py`

删除本地 `db_engine` fixture，并创建一个新的 fixture 来注册数据库资源。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_sql.py
~~~~~
~~~~~python.old
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver

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
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    engine.register(sqlite_db)
    return engine


@pytest.mark.asyncio
async def test_sql_query_success(db_engine):
    # Define a workflow using the 'sqlite_db' resource via explicit injection
    users = cs.sql("SELECT * FROM users ORDER BY name", conn=cs.inject("sqlite_db"))

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
~~~~~
~~~~~python.new
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
def db_engine(engine):
    engine.register(sqlite_db)
    return engine


@pytest.mark.asyncio
async def test_sql_query_success(db_engine):
    # Define a workflow using the 'sqlite_db' resource via explicit injection
    users = cs.sql("SELECT * FROM users ORDER BY name", conn=cs.inject("sqlite_db"))

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
~~~~~

#### Acts 3: 修复 `test_stdio.py`

删除本地 `engine` fixture。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_stdio.py
~~~~~
~~~~~python.old
import pytest
import cascade.sdk as cs
import io
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver


@pytest.fixture
def engine():
    return cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus())
~~~~~
~~~~~python.new
import pytest
import cascade.sdk as cs
import io
~~~~~

#### Acts 4: 修复 `test_time_provider.py`

删除本地 `engine` fixture。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_time_provider.py
~~~~~
~~~~~python.old
import time
import pytest
import cascade.sdk as cs

from cascade.runtime import Engine, EventBus
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor


@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=EventBus(),
    )
~~~~~
~~~~~python.new
import time
import pytest
import cascade.sdk as cs
~~~~~

### 下一步建议

我们已经完成了对 `cascade-library` 测试的全面清理。现在，所有已知的 `TypeError` 都应该已经解决。我将再次运行测试套件，期望所有测试都能通过。如果一切顺利，这次重构就可以标记为完成并准备提交了。
