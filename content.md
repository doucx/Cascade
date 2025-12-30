非常好。这些测试失败是**完全符合预期的**，它们精确地验证了我们上一步进行的 API 变更已经生效。测试用例现在就像一个“锁”，防止了旧的、不一致的 API 被意外使用，这正是测试驱动开发（TDD）的价值所在。

现在，我们的任务就是更新这些测试，使其与新的、更健壮的 API 契约保持一致。

---
1.  **`test_sql.py` 失败 (x3)**:
    *   **错误**: `TypeError: _sql_task() got an unexpected keyword argument 'db'`
    *   **原因**: 我们已经将 `cs.sql` 的 API 从 `cs.sql(..., db="resource_name")` 修改为了 `cs.sql(..., conn=cs.inject("resource_name"))`。测试代码仍在传递旧的 `db` 关键字参数，而新的底层任务 `_sql_task` 并不接受它，因此抛出 `TypeError`。

2.  **`test_ipfs.py` 失败 (x2)**:
    *   **错误**: `AttributeError: ... has no attribute 'IPFS_API_BASE_URL'`
    *   **原因**: 我们将 `ipfs` 提供者重构为了原子化的任务，并移除了模块级的全局常量 `IPFS_API_BASE_URL`，转而使用一个带有默认值的、可配置的任务参数 `api_base_url`。测试夹具 `mock_ipfs_server` 仍然试图通过 `monkeypatch` 修改那个已不存在的全局常量，因此引发 `AttributeError`。

---
## [WIP] fix: 更新测试用例以适应重构后的提供者 API

### 用户需求
修复因 `sql` 和 `ipfs` 提供者 API 变更而导致的单元测试失败。

### 评论
这是一次非常有价值的测试重构。对于 `sql` 测试，我们将使其明确地测试新的依赖注入模式。对于 `ipfs` 测试，我们将移除对全局状态的猴子补丁（monkeypatching），转而通过向任务传递参数来注入 mock URL。这使得测试更加健壮、隔离性更好，并且清晰地记录了任务的依赖关系，是测试实践的一次重要改进。

### 目标
1.  修改 `packages/cascade-library/tests/test_sql.py`，更新所有对 `cs.sql` 的调用，使用新的 `conn=cs.inject("resource_name")` API。
2.  增加一个新的测试用例，明确验证 `cs.sql` 对象本身是一个 `Task`（即拥有 `.map` 方法），以防止未来发生回归。
3.  修改 `packages/cascade-provider-ipfs/tests/test_ipfs.py`，调整 `mock_ipfs_server` 夹具，使其不再使用 `monkeypatch`，而是将 mock 服务器的 URL 作为参数传递给 `cs.ipfs.cat` 和 `cs.ipfs.add` 任务。

### 基本原理
我们将直接修改测试文件以匹配新的 API 签名。

*   对于 SQL 测试，这意味着将 `db="sqlite_db"` 替换为 `conn=cs.inject("sqlite_db")`。此外，由于 `_sql_factory` 被移除，我们需要确保 `sqlite_db` 资源 fixture 中使用的 `text` 函数来自 `sqlalchemy` 本身。
*   对于 IPFS 测试，这意味着 `mock_ipfs_server` 夹具将 `yield` 出 mock URL，测试函数接收这个 URL，并将其作为 `api_base_url` 参数传递给 `cs.ipfs.cat` 和 `cs.ipfs.add`。这是一种更清晰、更符合依赖注入原则的测试方式。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/architecture #task/object/provider-contract #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `test_sql.py`

我们将重写 `test_sql.py` 以使用新的 `conn=cs.inject(...)` 语法，并添加一个新测试来验证 `cs.sql` 现在是一个 `Task` 对象。

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
    assert hasattr(cs.sql, "map")
    assert hasattr(cs.sql, "with_retry")
    assert callable(cs.sql.map)
~~~~~

#### Acts 2: 修复 `test_ipfs.py`

我们将重写 `test_ipfs.py`，移除 `monkeypatch`，并显式地将 mock URL 传递给 `cs.ipfs` 任务。

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
async def mock_ipfs_server(aiohttp_client):
    app = web.Application()
    app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
    app.router.add_post("/api/v0/add", mock_ipfs_add_handler)
    client = await aiohttp_client(app)

    mock_base_url = f"http://{client.server.host}:{client.server.port}"
    yield mock_base_url


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
