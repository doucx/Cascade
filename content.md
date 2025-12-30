现在，我将生成一个计划来同时修复这两个问题。

## [WIP] fix: 修正测试用例中的 API 假设和异步 Fixture 问题

### 错误分析
1.  **`test_sql.py`**：测试用例错误地假设 `.with_retry` 方法存在于 `Task` 对象上。根据 `cascade` 的设计，策略方法（如 `with_retry`）应应用于调用 `Task` 后返回的 `LazyResult` 实例上。
2.  **`test_ipfs.py`**：测试环境无法正确处理 `async def` 类型的 fixture，导致 `pytest-asyncio` 报错。需要将 `mock_ipfs_server` fixture 改为同步定义，并在其内部使用事件循环来执行异步的服务器设置。

### 用户需求
修复所有失败的单元测试，使测试代码正确反映 `cascade` 的 API 设计，并适应当前的 `pytest` 测试环境。

### 评论
这次修复非常有价值。对于 SQL 测试，它纠正了我们对 Cascade 核心 DSL 设计的理解，并使测试能够准确地验证其真实行为。对于 IPFS 测试，它展示了如何在可能存在配置问题的 `pytest-asyncio` 环境中，通过一种更兼容的模式来编写 fixture，从而解决环境问题而不是逻辑问题，这增强了测试的健壮性。

### 目标
1.  修改 `packages/cascade-library/tests/test_sql.py`，纠正对 `Task` API 的错误断言，并添加一个新测试来验证正确的策略链式调用模式 (`cs.sql(...).with_retry(...)`)。
2.  修改 `packages/cascade-provider-ipfs/tests/test_ipfs.py`，将 `mock_ipfs_server` fixture 从 `async def` 改为 `def`，并使用 `event_loop` fixture 在内部同步地完成异步设置，以解决 `pytest` 的 fixture 兼容性问题。

### 基本原理
*   **SQL 测试**：我们将移除失败的 `assert hasattr(cs.sql, "with_retry")` 断言。`assert hasattr(cs.sql, "map")` 是正确的，将予以保留。然后，我们将添加一个新的测试用例，它调用 `cs.sql(...)` 得到一个 `LazyResult`，然后在这个 `LazyResult` 上调用 `.with_retry()`，并断言 `_retry_policy` 属性被正确设置。
*   **IPFS 测试**：我们将 `mock_ipfs_server` fixture 的签名改为 `def mock_ipfs_server(aiohttp_client, event_loop):`。在函数体内，我们使用 `event_loop.run_until_complete(aiohttp_client(app))` 来启动服务器，然后 `return` 或 `yield` mock URL。这样，fixture 本身对 `pytest` 来说是同步的，问题得以解决。测试函数本身保持 `async def` 不变。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/brainstorm #task/domain/architecture #task/object/provider-contract #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_sql.py` 的错误断言

我们将修正测试用例，使其正确反映 `Task` 和 `LazyResult` 的 API 职责。

~~~~~act
write_file
packages/cascade-library/tests/test_sql.py
~~~~~
~~~~~python
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
    # .map() is a method on the Task object itself
    assert hasattr(cs.sql, "map")
    assert callable(cs.sql.map)

    # .with_retry() is NOT on the Task, but on the LazyResult.
    assert not hasattr(cs.sql, "with_retry")


def test_sql_lazy_result_supports_policies():
    """
    Verify that the result of calling cs.sql(...) is a LazyResult
    that supports policy chaining.
    """
    # We don't need to run this, just check the type and methods.
    # A dummy connection is needed to satisfy the signature.
    lazy_result = cs.sql("SELECT 1", conn=cs.inject("dummy_db"))

    # Chain a policy method
    lazy_result_with_retry = lazy_result.with_retry(max_attempts=5)

    # Assert that the policy was attached
    assert lazy_result_with_retry._retry_policy is not None
    assert lazy_result_with_retry._retry_policy.max_attempts == 5
~~~~~

#### Acts 2: 修复 `test_ipfs.py` 的异步 Fixture 问题

我们将 `mock_ipfs_server` 改为同步 fixture，以适应测试环境。

~~~~~act
write_file
packages/cascade-provider-ipfs/tests/test_ipfs.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from aiohttp import web
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# The CID we will request in the test
TEST_CID = "QmZULkCELmmk5XNfCgTnflahDcwr9ssAAkAJd15uiNpdEp"
# The content our mock IPFS node will return for that CID
FAKE_CONTENT = b"hello ipfs world"
FAKE_ADD_RESPONSE = b'{"Name":"test.txt","Hash":"QmHash","Size":"16"}\n'


async def mock_ipfs_cat_handler(request: web.Request):
    if request.method != "POST":
        return web.Response(status=405)

    if request.query.get("arg") == TEST_CID:
        return web.Response(body=FAKE_CONTENT, content_type="application/octet-stream")
    else:
        return web.Response(status=404, text="CID not found")


async def mock_ipfs_add_handler(request: web.Request):
    if request.method != "POST":
        return web.Response(status=405)

    # Check if the request is multipart
    if not request.content_type.startswith("multipart/form-data"):
        return web.Response(status=400, text="Expected multipart/form-data")

    reader = await request.multipart()
    part = await reader.next()

    # We expect a part named 'file'
    if part and part.name != "file":
        return web.Response(status=400, text="Expected 'file' part")

    # Read content to verify
    if part:
        content = await part.read()
        if content != FAKE_CONTENT:
            return web.Response(status=400, text="Content mismatch")

    # Return standard IPFS add JSON response
    return web.Response(body=FAKE_ADD_RESPONSE, content_type="application/json")


@pytest.fixture
def mock_ipfs_server(aiohttp_client, event_loop):
    app = web.Application()
    app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
    app.router.add_post("/api/v0/add", mock_ipfs_add_handler)

    # Use the event_loop fixture from pytest-asyncio to run the async setup
    # inside our synchronous fixture.
    client = event_loop.run_until_complete(aiohttp_client(app))

    mock_base_url = f"http://{client.server.host}:{client.server.port}"
    return mock_base_url


@pytest.mark.asyncio
async def test_ipfs_cat_provider(mock_ipfs_server):
    # Define the Cascade workflow, passing the mock URL explicitly
    workflow = cs.ipfs.cat(cid=TEST_CID, api_base_url=mock_ipfs_server)

    # Run the workflow
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert the result
    assert result == FAKE_CONTENT


@pytest.mark.asyncio
async def test_ipfs_add_provider(mock_ipfs_server, tmp_path):
    # Create a temporary file to upload
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(FAKE_CONTENT)

    # Define workflow, passing the mock URL explicitly
    workflow = cs.ipfs.add(path=str(test_file), api_base_url=mock_ipfs_server)

    # Run
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
    assert result == "QmHash"
~~~~~
