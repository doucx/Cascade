## [WIP] fix: 采用 `get_running_loop` 修复 `pytest-asyncio` fixture 问题

### 错误分析
上一个计划中对 `test_ipfs.py` 的修复引入了一个新错误：`fixture 'event_loop' not found`。这是因为 `pytest-asyncio` 在当前配置下没有将 `event_loop` 作为一个可注入的 fixture 提供。试图将 `mock_ipfs_server` fixture 改为同步定义并请求 `event_loop` 的策略因此失败。

### 用户需求
修复 `test_ipfs.py` 中的 `fixture 'event_loop' not found` 错误，同时确保测试能够正确设置异步的 mock 服务器。

### 评论
这是一个经典的测试环境适配问题。通过使用 `asyncio.get_running_loop()`，我们编写的 fixture 代码变得更加通用和健壮，因为它不再依赖于 `pytest-asyncio` 插件注入特定名称的 fixture，而是直接与正在运行的事件循环进行交互。这是一个更优雅、更可靠的解决方案。

### 目标
1.  修改 `packages/cascade-provider-ipfs/tests/test_ipfs.py` 中的 `mock_ipfs_server` fixture。
2.  将其实现改为：保持为同步函数 (`def`)，内部通过 `asyncio.get_running_loop()` 获取事件循环，并使用 `loop.run_until_complete()` 来执行异步的服务器设置。

### 基本原理
我们将 `mock_ipfs_server` fixture 的实现替换为一个不接受 `event_loop` 参数的同步函数。在该函数内部，我们定义一个 `async` 辅助函数来包含所有需要 `await` 的逻辑（如 `aiohttp_client(app)`）。然后，我们获取当前正在运行的事件循环，并用它来同步执行这个辅助函数，最后返回其结果。这样，从 `pytest` 的角度看，fixture 是同步的，但它成功地完成了所有异步设置任务。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/async-fixture #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_ipfs.py` 的 fixture 实现

我们将重写 `mock_ipfs_server` fixture，使其不再依赖于注入的 `event_loop`。

~~~~~act
write_file
packages/cascade-provider-ipfs/tests/test_ipfs.py
~~~~~
~~~~~python
import pytest
import asyncio
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
def mock_ipfs_server(aiohttp_client):
    # This fixture is synchronous from pytest's perspective.
    # We get the running loop managed by pytest-asyncio to set up our async server.
    loop = asyncio.get_running_loop()

    async def setup():
        app = web.Application()
        app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
        app.router.add_post("/api/v0/add", mock_ipfs_add_handler)
        client = await aiohttp_client(app)
        return f"http://{client.server.host}:{client.server.port}"

    # Run the async setup on the current event loop and return the result.
    return loop.run_until_complete(setup())


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
