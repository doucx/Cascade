import pytest
import cascade as cs
import aiohttp
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if aiohttp is not installed
pytest.importorskip("aiohttp")


@pytest.mark.asyncio
async def test_http_get_success(aiohttp_client):
    """
    Tests a successful GET request using a mocked server.
    """

    # 1. Mock Server Setup
    async def handler(request):
        from aiohttp import web

        return web.json_response({"user": "cascade"})

    app = aiohttp.web.Application()
    app.router.add_get("/api/user", handler)
    client = await aiohttp_client(app)

    # 2. Define Cascade workflow
    # Note: cs.http is loaded dynamically by __getattr__
    api_response = cs.http(
        f"{client.server.scheme}://{client.server.host}:{client.server.port}/api/user"
    )

    @cs.task
    def process_user(res):
        # The new .json() method directly returns a parsed dict
        data = res.json()
        return data["user"]

    final_result = process_user(api_response)

    # 3. Run and Assert
    # Since we are already in an async test loop, we use the Engine directly
    # instead of cs.run() which tries to create a new loop via asyncio.run()
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_result)
    assert result == "cascade"


@pytest.mark.asyncio
async def test_http_with_template(aiohttp_client):
    """
    Tests that cs.http works correctly with cs.template for dynamic URLs.
    """

    # 1. Mock Server
    async def user_handler(request):
        from aiohttp import web

        username = request.match_info["name"]
        return web.json_response({"user": username, "status": "ok"})

    app = aiohttp.web.Application()
    app.router.add_get("/users/{name}", user_handler)
    client = await aiohttp_client(app)

    # 2. Workflow
    username_param = cs.Param("username", default="testuser")

    base_url = f"{client.server.scheme}://{client.server.host}:{client.server.port}"

    # Build URL dynamically
    api_url = cs.template(
        "{{ base }}/users/{{ user }}", base=base_url, user=username_param
    )

    api_response = cs.http(api_url)

    @cs.task
    def get_status(res):
        # The .json() method is now sync and returns a parsed dict.
        # The task no longer needs to be async.
        return res.json()["status"]

    final_status = get_status(api_response)

    # 3. Run and Assert
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
