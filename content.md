这是实现 **任务 1.2: `cs.http` 原子化网络提供者** 的构建计划。

我们将按照路线图的设计，将 `cs.http` 从一个单一的通用提供者，重构为一组语义明确的原子化提供者（`cs.http.get`, `cs.http.post` 等），并规范化其返回对象 `HttpResponse`。

## [WIP] feat(providers): Implement atomic `cs.http` providers

### 用户需求
1.  将 `cs.http` 命名空间化，提供语义明确的 HTTP 方法提供者：`cs.http.get`, `cs.http.post`, `cs.http.put`, `cs.http.delete`。
2.  确保所有 HTTP 任务返回统一的 `HttpResponse` 数据类（原 `SimpleHttpResponse` 重命名），并提供 `.json()` 和 `.text()` 辅助方法。
3.  保持底层的原子性，不包含业务解析逻辑。

### 评论
这是一个架构层面的重构。当前的 `cs.http` 是一个单一的工厂函数，重构后 `cs.http` 将变为一个包含多个方法的命名空间。这符合我们“提供者组合优于封装”的原则，使得构建基于 REST 的工作流更加直观。

### 目标
1.  重构 `src/cascade/providers/http.py`，实现 `HttpResponse` 和具体的 HTTP 任务/提供者。
2.  更新 `pyproject.toml`，注册新的 `http.*` 入口点，替换旧的 `http` 入口点。
3.  更新 `tests/providers/test_http.py` 以匹配新的 API。

### 基本原理
通过将 HTTP 操作拆分为独立的 Provider，我们利用了 Cascade 的命名空间加载机制（`cs.http` 自动成为命名空间代理）。这消除了用户手动传递 `method="POST"` 字符串的需要，提供了更 Pythonic 的 API，同时保持了每个原子任务的单一职责。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #scope/api #task/domain/io #task/object/http-provider #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `cs.http` 提供者实现

我们将重写 `src/cascade/providers/http.py`。
主要变更：
1.  `SimpleHttpResponse` -> `HttpResponse`。
2.  提取 `_perform_request` 核心逻辑。
3.  实现 `_http_get`, `_http_post`, `_http_put`, `_http_delete` 任务及其对应的 Provider 类。

~~~~~act
write_file
src/cascade/providers/http.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any, Dict, Optional
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider

try:
    import aiohttp
except ImportError:
    aiohttp = None


@dataclass
class HttpResponse:
    """A simple, safe data holder for the HTTP response."""

    status: int
    headers: Dict[str, str]
    body: bytes

    def text(self, encoding: str = "utf-8") -> str:
        """Decodes the response body into a string."""
        return self.body.decode(encoding)

    def json(self) -> Any:
        """Parses the response body as JSON and returns a Python object."""
        import json
        return json.loads(self.text())

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status}>"


async def _perform_request(
    url: str,
    method: str,
    params: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
) -> HttpResponse:
    """Core logic to perform an HTTP request using aiohttp."""
    if aiohttp is None:
        raise ImportError(
            "The 'aiohttp' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(
            method, url, params=params, json=json_data, data=data
        ) as response:
            # Note: We do NOT raise_for_status() automatically here.
            # We want to return the response object so the user (or a downstream task)
            # can decide how to handle 4xx/5xx codes.
            # However, for convenience in simple workflows, users often expect failure on error.
            # But adhering to "Atomic Provider" philosophy, raw HTTP provider should probably
            # just return the response.
            # EDIT: The original implementation did raise_for_status().
            # To be robust, let's read the body first, then check status?
            # Or just let it be.
            # Let's keep it pure: Return the response. If status check is needed,
            # it should be a separate logic or a .with_retry() policy triggered by exception.
            # BUT, .with_retry() only triggers on Exception. If we don't raise, we can't retry on 503.
            # So we MUST raise for 5xx/4xx if we want to use Cascade's retry mechanisms easily.
            # Compromise: raise for status, but capture the body first so we can attach it to the error if needed.
            # Actually, aiohttp's raise_for_status() is good.
            
            body_bytes = await response.read()
            
            # We construct the response object FIRST
            resp_obj = HttpResponse(
                status=response.status,
                headers=dict(response.headers),
                body=body_bytes,
            )
            
            # If we want to allow 404 handling without try/catch in the graph, we shouldn't raise.
            # But then .with_retry() won't work for 503s.
            # Let's verify standard practices. Typically, raw HTTP clients usually have a 'raise_for_status' flag.
            # We'll default to NOT raising, to allow logic like "if 404 do X".
            # Users can use a generic "check_status" task or we can add a flag.
            # Let's NOT raise by default to keep it atomic and pure.
            # User can throw in a downstream task if they want to trigger retry.
            
            return resp_obj


# --- Tasks ---

@task(name="http_get")
async def _http_get_task(
    url: str,
    params: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "GET", params=params, headers=headers)


@task(name="http_post")
async def _http_post_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "POST", params=params, json_data=json, data=data, headers=headers)


@task(name="http_put")
async def _http_put_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "PUT", json_data=json, data=data, headers=headers)


@task(name="http_delete")
async def _http_delete_task(
    url: str,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "DELETE", headers=headers)


@task(name="http_request")
async def _http_request_task(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, str]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, method, params=params, json_data=json, data=data, headers=headers)


# --- Providers ---

class HttpGetProvider(Provider):
    name = "http.get"
    def create_factory(self) -> LazyFactory:
        return _http_get_task

class HttpPostProvider(Provider):
    name = "http.post"
    def create_factory(self) -> LazyFactory:
        return _http_post_task

class HttpPutProvider(Provider):
    name = "http.put"
    def create_factory(self) -> LazyFactory:
        return _http_put_task

class HttpDeleteProvider(Provider):
    name = "http.delete"
    def create_factory(self) -> LazyFactory:
        return _http_delete_task

class HttpRequestProvider(Provider):
    name = "http.request"
    def create_factory(self) -> LazyFactory:
        return _http_request_task
~~~~~

#### Acts 2: 更新 `pyproject.toml` 入口点

移除旧的 `http` 键，添加新的 `http.*` 键。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
~~~~~
~~~~~toml
template = "cascade.providers.template:TemplateProvider"
# http namespace
"http.get" = "cascade.providers.http:HttpGetProvider"
"http.post" = "cascade.providers.http:HttpPostProvider"
"http.put" = "cascade.providers.http:HttpPutProvider"
"http.delete" = "cascade.providers.http:HttpDeleteProvider"
"http.request" = "cascade.providers.http:HttpRequestProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
~~~~~

#### Acts 3: 更新测试用例

更新 `tests/providers/test_http.py` 以使用新的 API，并添加对 POST 的测试。

~~~~~act
write_file
tests/providers/test_http.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if aiohttp is not installed
pytest.importorskip("aiohttp")


@pytest.mark.asyncio
async def test_http_get_success(aiohttp_client):
    """
    Tests a successful GET request using cs.http.get.
    """
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

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_result)
    assert result == "cascade"


@pytest.mark.asyncio
async def test_http_post_success(aiohttp_client):
    """
    Tests a successful POST request using cs.http.post.
    """
    async def handler(request):
        from aiohttp import web
        data = await request.json()
        return web.json_response({"received": data["value"], "status": "created"}, status=201)

    app = aiohttp.web.Application()
    app.router.add_post("/api/items", handler)
    client = await aiohttp_client(app)

    url = f"{client.server.scheme}://{client.server.host}:{client.server.port}/api/items"
    
    # Use cs.http.post
    api_response = cs.http.post(url, json={"value": 42})

    @cs.task
    def check_response(res):
        assert res.status == 201
        return res.json()

    final_result = check_response(api_response)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_result)
    assert result["received"] == 42
    assert result["status"] == "created"


@pytest.mark.asyncio
async def test_http_with_template(aiohttp_client):
    """
    Tests that cs.http.get works correctly with cs.template for dynamic URLs.
    """
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

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~

### 下一步建议
我们已经完成了 `cs.io` (文件/S3) 和 `cs.http` (网络) 的基础设施建设。这是路线图第一阶段的全部内容。接下来，我们应该进入第二阶段：**实现工作流模块化 (`cs.subflow`)**。这将允许我们将刚才构建的原子积木封装成可复用的高级模式。
