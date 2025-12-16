import pytest
import cascade as cs

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
    api_response = cs.http(f"{client.server.scheme}://{client.server.host}:{client.server.port}/api/user")

    @cs.task
    def process_user(res):
        # The response object from http task has a .json() method
        import json
        data = json.loads(res.json()) # The body is bytes, so we parse it
        return data["user"]

    final_result = process_user(api_response)

    # 3. Run and Assert
    result = cs.run(final_result)
    assert result == "cascade"


@pytest.mark.asyncio
async def test_http_with_template(aiohttp_client):
    """
    Tests that cs.http works correctly with cs.template for dynamic URLs.
    """
    # 1. Mock Server
    async def user_handler(request):
        from aiohttp import web
        username = request.match_info['name']
        return web.json_response({"user": username, "status": "ok"})

    app = aiohttp.web.Application()
    app.router.add_get("/users/{name}", user_handler)
    client = await aiohttp_client(app)

    # 2. Workflow
    username_param = cs.Param("username", default="testuser")
    
    base_url = f"{client.server.scheme}://{client.server.host}:{client.server.port}"

    # Build URL dynamically
    api_url = cs.template(
        "{{ base }}/users/{{ user }}",
        base=base_url,
        user=username_param
    )
    
    api_response = cs.http(api_url)

    @cs.task
    async def get_status(res):
        # We need to make this task async to call await on res.json()
        # The executor should handle this. Let's re-verify the http.py implementation
        # Ah, my implementation of SimpleHttpResponse.json() is not async. Let's fix that.
        import json
        return json.loads(res.json())['status']

    final_status = get_status(api_response)
    
    # 3. Run and Assert
    result = cs.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"