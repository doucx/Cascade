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
    if part.name != "file":
        return web.Response(status=400, text="Expected 'file' part")

    # Read content to verify
    content = await part.read()
    if content != FAKE_CONTENT:
        return web.Response(status=400, text="Content mismatch")

    # Return standard IPFS add JSON response
    return web.Response(body=FAKE_ADD_RESPONSE, content_type="application/json")


@pytest.fixture
def mock_ipfs_server(aiohttp_client, monkeypatch):
    async def _setup():
        app = web.Application()
        app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
        app.router.add_post("/api/v0/add", mock_ipfs_add_handler)
        client = await aiohttp_client(app)

        mock_base_url = f"http://{client.server.host}:{client.server.port}"
        monkeypatch.setattr(
            "cascade.providers.ipfs.provider.IPFS_API_BASE_URL", mock_base_url
        )
        return client

    return _setup


@pytest.mark.asyncio
async def test_ipfs_cat_provider(mock_ipfs_server):
    await mock_ipfs_server()

    # Define the Cascade workflow
    workflow = cs.ipfs.cat(cid=TEST_CID)

    # Run the workflow
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert the result
    assert result == FAKE_CONTENT


@pytest.mark.asyncio
async def test_ipfs_add_provider(mock_ipfs_server, tmp_path):
    await mock_ipfs_server()

    # Create a temporary file to upload
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(FAKE_CONTENT)

    # Define workflow
    workflow = cs.ipfs.add(path=str(test_file))

    # Run
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    result = await engine.run(workflow)

    # Assert we got the hash from the JSON response
    assert result == "QmHash"
