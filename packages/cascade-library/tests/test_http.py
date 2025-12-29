import pytest
import cascade as cs
import aiohttp
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if aiohttp is not installed
pytest.importorskip("aiohttp")


@pytest.mark.asyncio
async def test_http_get_success(aiohttp_client):
    async def handler(request):
        from aiohttp import web

        return web.json_response({"user": "cascade"})

    app = aiohttp.web.Application()
    app.router.add_get("/api/user", handler)
    client = await aiohttp_client(app)

    # Use cs.http.get
    url = f"{client.server.scheme}://{client.server.host}:{client.server.port}/api/user"
    api_response = cs.http.get(url)

    @cs.task
    def process_user(res):
        # res is HttpResponse
        data = res.json()
        return data["user"]

    final_result = process_user(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(final_result)
    assert result == "cascade"


@pytest.mark.asyncio
async def test_http_post_success(aiohttp_client):
    async def handler(request):
        from aiohttp import web

        data = await request.json()
        return web.json_response(
            {"received": data["value"], "status": "created"}, status=201
        )

    app = aiohttp.web.Application()
    app.router.add_post("/api/items", handler)
    client = await aiohttp_client(app)

    url = (
        f"{client.server.scheme}://{client.server.host}:{client.server.port}/api/items"
    )

    # Use cs.http.post
    api_response = cs.http.post(url, json={"value": 42})

    @cs.task
    def check_response(res):
        assert res.status == 201
        return res.json()

    final_result = check_response(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(final_result)
    assert result["received"] == 42
    assert result["status"] == "created"


@pytest.mark.asyncio
async def test_http_with_template(aiohttp_client):
    async def user_handler(request):
        from aiohttp import web

        username = request.match_info["name"]
        return web.json_response({"user": username, "status": "ok"})

    app = aiohttp.web.Application()
    app.router.add_get("/users/{name}", user_handler)
    client = await aiohttp_client(app)

    username_param = cs.Param("username", default="testuser")
    base_url = f"{client.server.scheme}://{client.server.host}:{client.server.port}"

    api_url = cs.template(
        "{{ base }}/users/{{ user }}", base=base_url, user=username_param
    )

    api_response = cs.http.get(api_url)

    @cs.task
    def get_status(res):
        return res.json()["status"]

    final_status = get_status(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
