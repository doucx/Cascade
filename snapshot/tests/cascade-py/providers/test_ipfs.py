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


async def mock_ipfs_cat_handler(request: web.Request):
    """A mock aiohttp handler for the `ipfs cat` RPC call."""
    if request.method != "POST":
        return web.Response(status=405)
    
    if request.query.get("arg") == TEST_CID:
        return web.Response(body=FAKE_CONTENT, content_type="application/octet-stream")
    else:
        return web.Response(status=404, text="CID not found")


@pytest.mark.asyncio
async def test_ipfs_cat_provider(aiohttp_client, monkeypatch):
    """
    Tests the cs.ipfs.cat provider by mocking the IPFS HTTP API.
    """
    # 1. Setup the mock server
    app = web.Application()
    app.router.add_post("/api/v0/cat", mock_ipfs_cat_handler)
    client = await aiohttp_client(app)
    
    # 2. Monkeypatch the IPFS provider to point to our mock server
    # The URL is constructed inside the provider, so we patch the base URL constant there.
    mock_base_url = f"http://{client.server.host}:{client.server.port}"
    monkeypatch.setattr(
        "cascade.providers.ipfs.provider.IPFS_API_BASE_URL", 
        mock_base_url
    )

    # 3. Define the Cascade workflow
    # This will dynamically load the `cs.ipfs.cat` provider via entry points
    workflow = cs.ipfs.cat(cid=TEST_CID)

    # 4. Run the workflow using the async Engine directly
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus() # A silent bus for clean test output
    )
    result = await engine.run(workflow)

    # 5. Assert the result
    assert result == FAKE_CONTENT