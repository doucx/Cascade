## [WIP] refactor(library): migrate http provider from aiohttp to httpx

### 错误分析
在之前的尝试中，我生成的 `patch_file` 指令块格式不完整（缺少 `old_string` 和 `new_string` 参数块），导致 Quipu 运行时无法执行修改。本次计划将修正此错误。

### 用户需求
将 `cascade-library` 包中的 HTTP Provider 实现从 `aiohttp` 迁移到 `httpx`。

### 评论
迁移到 `httpx` 能显著提升代码的现代感和可维护性。由于 `cascade-library` 封装了 `HttpResponse`，我们可以确保这种底层库的更替不会对上层业务逻辑（即计算图中的任务流）造成破坏性影响。

### 目标
1.  修改 `pyproject.toml` 中的扩展依赖，用 `httpx` 替换 `aiohttp`。
2.  重写 `cascade.providers.http` 模块，使用 `httpx.AsyncClient` 重新实现请求逻辑。
3.  更新测试文件，增加对 `httpx` 的环境检查，同时保留 `aiohttp` 以维持 Mock Server 的运行。

### 基本原理
1.  **代码重构**: 弃用 `aiohttp.ClientSession`。`httpx.AsyncClient` 的 `request` 方法更简洁，且对 multipart 数据（files）的封装更自动化。
2.  **兼容性维护**: `HttpResponse` 作为 DTO（数据传输对象）保持不变。我们将映射 `httpx.Response.status_code` 到 `HttpResponse.status`。
3.  **测试策略**: 现有的 `aiohttp_client` 插件依然非常适合作为轻量级本地服务器进行集成测试，因此测试环境将同时要求这两个库。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #task/domain/io #task/object/http-provider #task/action/migration #task/state/begin

---

### Script

#### Acts 1: 更新项目依赖 (Corrected Patch)

我们将 `aiohttp` 替换为 `httpx`。

~~~~~act
patch_file
packages/cascade-library/pyproject.toml
~~~~~
~~~~~toml.old
[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-runtime[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer",
  "PyYAML",
  "aiobotocore",
  "cascade-runtime[redis]",
]
~~~~~
~~~~~toml.new
[project.optional-dependencies]
template = ["jinja2"]
http = ["httpx"]
sql = ["sqlalchemy"]
cli = ["typer"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-runtime[redis]"]
all = [
  "jinja2",
  "httpx",
  "sqlalchemy",
  "typer",
  "PyYAML",
  "aiobotocore",
  "cascade-runtime[redis]",
]
~~~~~

#### Acts 2: 重构 HTTP Provider 实现 (Complete Rewrite)

我们将重写 `http.py` 以适应 `httpx` 的 API。

~~~~~act
write_file
packages/cascade-library/src/cascade/providers/http.py
~~~~~
~~~~~python
import os
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, Tuple, IO
from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider

try:
    import httpx
except ImportError:
    httpx = None


@dataclass
class HttpResponse:
    status: int
    headers: Dict[str, str]
    body: bytes

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)

    def json(self) -> Any:
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
    files: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    if httpx is None:
        raise ImportError(
            "The 'httpx' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    # Use ExitStack to ensure any files opened for upload are closed
    with ExitStack() as stack:
        # Prepare files for httpx
        httpx_files: Optional[Dict[str, Union[IO[bytes], Tuple[str, IO[bytes]]]]] = None
        
        if files:
            httpx_files = {}
            for field_name, file_path in files.items():
                if isinstance(file_path, str) and os.path.exists(file_path):
                    f = stack.enter_context(open(file_path, "rb"))
                    httpx_files[field_name] = (os.path.basename(file_path), f)
                else:
                    httpx_files[field_name] = file_path  # type: ignore

        # In httpx, if 'data' is a dict and 'files' is present, it handles multipart/form-data.
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                data=data,
                files=httpx_files,
            )
            
            # Construct the response object
            resp_obj = HttpResponse(
                status=response.status_code,
                headers=dict(response.headers),
                body=response.content,
            )

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
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url,
        "POST",
        params=params,
        json_data=json,
        data=data,
        files=files,
        headers=headers,
    )


@task(name="http_put")
async def _http_put_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url, "PUT", json_data=json, data=data, files=files, headers=headers
    )


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
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url,
        method,
        params=params,
        json_data=json,
        data=data,
        files=files,
        headers=headers,
    )


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

#### Acts 3: 更新测试用例导入逻辑 (Corrected Patch)

我们需要清理掉 `aiohttp` 在测试逻辑中的直接使用（仅保留 Mock Server 的部分）。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
import aiohttp
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.kernel.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if aiohttp is not installed
pytest.importorskip("aiohttp")
~~~~~
~~~~~python.new
import pytest
import cascade as cs
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.kernel.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if dependencies are not installed
pytest.importorskip("aiohttp") # For the mock server fixture (aiohttp_client)
pytest.importorskip("httpx")   # For the code under test (cascade-library)
~~~~~

### 下一步建议
迁移完成后，建议运行以下命令进行验证：
1.  `pip install ./packages/cascade-library[http]`（确保安装了 `httpx`）。
2.  `pytest packages/cascade-library/tests/integration/test_http.py`（确保集成测试通过）。
