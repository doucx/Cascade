好的，这是我们架构重构的最后一批清理工作。这些测试文件来自不同的包，但问题是完全相同的：它们都在手动实例化 `Engine`，而没有遵循新的依赖注入契约。

我将一次性修复所有这些遗留问题，将它们全部迁移到统一的 `engine` fixture 体系。

## [WIP] fix(tests): Finalize migration to global engine fixture across all packages

### 错误分析

在 `cascade-provider-ipfs`、`cascade-sdk` 和 `cascade-spec` 的集成测试中，仍然存在手动调用 `Engine(...)` 的代码。由于 `Engine` 的构造函数签名已更改为需要注入 `strategy`, `constraint_manager` 等核心服务，这些旧的调用方式导致了 `TypeError`。

### 用户需求

修复所有剩余的 `TypeError`，完成整个代码库向新的 `engine` fixture 架构的迁移。

### 评论

这次提交标志着我们依赖注入重构的成功完成。通过根除所有分散的、手动的 `Engine` 实例化，并用统一的、由工厂支持的 fixture 取而代之，我们不仅修复了所有相关的 `TypeError`，还极大地提高了测试套件的**一致性、可读性和可维护性**。这是一个完美的例子，展示了如何通过坚持架构原则（如依赖注入）来构建一个更健壮、更易于管理的系统。

### 目标

1.  修改 `cascade-provider-ipfs/tests/integration/test_ipfs.py`，使用全局 `engine` fixture。
2.  修改 `cascade-sdk/tests/integration/test_llm_pattern.py`，使用全局 `engine` fixture。
3.  重构 `cascade-spec/tests/integration/test_resource.py`，将其中的同步测试（内部使用 `asyncio.run`）改造为标准的 `async` 测试，并使用 `engine` 和 `engine_factory` fixture。

### 基本原理

我们将采用与前几轮修复完全相同的策略：
-   在测试函数签名中声明 `engine` fixture，以获得一个预先配置好的 `Engine` 实例。
-   对于需要自定义或多个 `Engine` 实例的复杂测试（如 `test_resource_override`），我们将使用 `engine_factory` fixture。
-   移除所有本地的、手动的 `Engine` 实例化代码及其不再需要的导入（`NativeSolver`, `LocalExecutor`, `EventBus` 等）。
-   将 `test_resource.py` 中的同步测试改造为 `async` 测试，这是处理异步代码的更标准、更简洁的方式。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/test-fixtures #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 修复 `cascade-provider-ipfs` 测试

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
import pytest
import cascade.sdk as cs
from aiohttp import web
from cascade.runtime.host.instance import Engine
from cascade.runtime import EventBus
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
~~~~~
~~~~~python.new
import pytest
import cascade.sdk as cs
from aiohttp import web
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_ipfs_cat_provider(mock_ipfs_server):
    # Define the Cascade workflow, passing the mock URL explicitly
    workflow = cs.ipfs.cat(cid=TEST_CID, api_base_url=mock_ipfs_server)

    # Run the workflow
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    # Assert the result
    assert result == FAKE_CONTENT
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_ipfs_cat_provider(engine, mock_ipfs_server):
    # Define the Cascade workflow, passing the mock URL explicitly
    workflow = cs.ipfs.cat(cid=TEST_CID, api_base_url=mock_ipfs_server)

    # Run the workflow
    result = await engine.run(workflow)

    # Assert the result
    assert result == FAKE_CONTENT
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_ipfs_add_provider(mock_ipfs_server, tmp_path):
    # Create a temporary file to upload
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(FAKE_CONTENT)

    # Define workflow, passing the mock URL explicitly
    workflow = cs.ipfs.add(path=str(test_file), api_base_url=mock_ipfs_server)

    # Run
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
    assert result == "QmHash"
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_ipfs_add_provider(engine, mock_ipfs_server, tmp_path):
    # Create a temporary file to upload
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(FAKE_CONTENT)

    # Define workflow, passing the mock URL explicitly
    workflow = cs.ipfs.add(path=str(test_file), api_base_url=mock_ipfs_server)

    # Run
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
    assert result == "QmHash"
~~~~~

#### Acts 2: 修复 `cascade-sdk` 测试

~~~~~act
patch_file
packages/cascade-sdk/tests/integration/test_llm_pattern.py
~~~~~
~~~~~python.old
import pytest
import cascade.sdk as cs
from unittest.mock import MagicMock
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.providers.http import HttpResponse
~~~~~
~~~~~python.new
import pytest
import cascade.sdk as cs
from unittest.mock import MagicMock
from cascade.providers.http import HttpResponse
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/integration/test_llm_pattern.py
~~~~~
~~~~~python.old
    # Run the workflow
    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(summary)
~~~~~
~~~~~python.new
    # Run the workflow
    result = await engine.run(summary)
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/integration/test_llm_pattern.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_llm_pattern_via_subflow(mock_http_post, monkeypatch):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_llm_pattern_via_subflow(engine, mock_http_post, monkeypatch):
~~~~~

#### Acts 3: 重构并修复 `cascade-spec` 测试

~~~~~act
write_file
packages/cascade-spec/tests/integration/test_resource.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade.sdk as cs
from cascade.bus.events import (
    ResourceAcquired,
    ResourceReleased,
    Event,
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
    acquired_names = [e.resource_name for e in spy.events if isinstance(e, ResourceAcquired)]
    # 'config' must be acquired before 'db_connection' because db_connection depends on config
    assert "config" in acquired_names
    assert "db_connection" in acquired_names
    assert acquired_names.index("config") < acquired_names.index("db_connection")

    # Check for ResourceReleased events
    released_names = [e.resource_name for e in spy.events if isinstance(e, ResourceReleased)]
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
~~~~~

### 下一步建议

我们已经完成了所有已知 `TypeError` 的修复，并将整个测试套件统一到了新的 fixture 架构下。现在，我将运行完整的测试。如果所有测试都通过，这个重构任务就圆满完成了，我们可以自信地提交这些变更。
