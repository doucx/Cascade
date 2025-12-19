船长，看来在之前的航行中，我们的测试脚本遭遇了“代码残留”——在 `patch_file` 的过程中，一段旧的、带有语法错误的代码块被意外地追加到了文件末尾。这导致了 `test_ipfs_add_provider` 的失败。

我将立即生成一个计划来清理这个烂摊子，恢复测试文件的纯净。

## [WIP] fix: 清理 IPFS 测试文件中的重复和错误代码

### 错误分析
在 `tests/cascade-py/providers/test_ipfs.py` 的末尾（第 116 行以后），存在一段重复且格式错误的 `test_ipfs_cat_provider` 逻辑。这段代码：
1.  **不在任何函数内**: 它直接暴露在模块层级。
2.  **引用了未定义的变量**: 它使用了 `aiohttp_client` 和 `monkeypatch`，而这些变量只有在作为 `pytest` fixture 传入函数时才有效。
3.  **导致执行中断**: `pytest` 在解析模块时遇到这些错误，导致 `test_ipfs_add_provider` 无法正常完成或报错。

### 用户需求
彻底清理 `tests/cascade-py/providers/test_ipfs.py`，移除末尾的冗余代码，确保两个测试用例（`cat` 和 `add`）都能在干净的环境中运行。

### 评论
这是典型的“代码熵”增加。在快速迭代中，`patch_file` 有时会因为定位锚点模糊而产生这种副作用。通过 `write_file` 进行全量覆盖是将其恢复到有序状态的最快、最彻底的方法。

### 目标
1.  全量重写 `tests/cascade-py/providers/test_ipfs.py`。
2.  保留已验证正确的 `mock_ipfs_server` fixture 和两个测试函数。
3.  移除文件末尾的所有垃圾代码。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/ipfs-provider #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 清理测试文件

我们通过全量写入来确保文件的完整性和正确性。

~~~~~act
write_file
tests/cascade-py/providers/test_ipfs.py
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
    """A mock aiohttp handler for the `ipfs cat` RPC call."""
    if request.method != "POST":
        return web.Response(status=405)
    
    if request.query.get("arg") == TEST_CID:
        return web.Response(body=FAKE_CONTENT, content_type="application/octet-stream")
    else:
        return web.Response(status=404, text="CID not found")


async def mock_ipfs_add_handler(request: web.Request):
    """A mock aiohttp handler for the `ipfs add` RPC call."""
    if request.method != "POST":
        return web.Response(status=405)

    # Check if the request is multipart
    if not request.content_type.startswith("multipart/form-data"):
        return web.Response(status=400, text="Expected multipart/form-data")

    reader = await request.multipart()
    part = await reader.next()
    
    # We expect a part named 'file'
    if part.name != 'file':
        return web.Response(status=400, text="Expected 'file' part")
    
    # Read content to verify
    content = await part.read()
    if content != FAKE_CONTENT:
        return web.Response(status=400, text="Content mismatch")

    # Return standard IPFS add JSON response
    return web.Response(body=FAKE_ADD_RESPONSE, content_type="application/json")


@pytest.fixture
def mock_ipfs_server(aiohttp_client, monkeypatch):
    """Fixture to setup the mock IPFS server and patch the provider."""
    async def _setup():
        app = web.Application()
        app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
        app.router.add_post("/api/v0/add", mock_ipfs_add_handler)
        client = await aiohttp_client(app)
        
        mock_base_url = f"http://{client.server.host}:{client.server.port}"
        monkeypatch.setattr(
            "cascade.providers.ipfs.provider.IPFS_API_BASE_URL", 
            mock_base_url
        )
        return client
    return _setup


@pytest.mark.asyncio
async def test_ipfs_cat_provider(mock_ipfs_server):
    """
    Tests the cs.ipfs.cat provider.
    """
    await mock_ipfs_server()

    # Define the Cascade workflow
    workflow = cs.ipfs.cat(cid=TEST_CID)

    # Run the workflow
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus()
    )
    result = await engine.run(workflow)

    # Assert the result
    assert result == FAKE_CONTENT


@pytest.mark.asyncio
async def test_ipfs_add_provider(mock_ipfs_server, tmp_path):
    """
    Tests the cs.ipfs.add provider with local file upload.
    """
    await mock_ipfs_server()

    # Create a temporary file to upload
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(FAKE_CONTENT)

    # Define workflow
    workflow = cs.ipfs.add(path=str(test_file))

    # Run
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus()
    )
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
    assert result == "QmHash"
~~~~~

### 下一步建议
文件已清理。请重新运行测试套件。

这一次，所有的 IPFS 集成测试（`cat` 和 `add`）都应该能顺利通过，证明了我们通过组合 `cs.http` 实现 IPFS 功能的策略是完全成功的。一旦通过，我们将迈向里程碑 5.2 的终章：**实现基于 IPFS 的缓存后端**。
