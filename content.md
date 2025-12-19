这是一个严重的格式错误，是由于 `patch_file` 在处理多层嵌套缩进时应用不当导致的。这种错误会直接阻止 Python 解析器加载模块。

我将立即通过完全重写该文件来修复此问题，以确保缩进结构的绝对正确性。

## [WIP] fix: 修复 `cs.http` 提供者中的严重缩进错误

### 用户需求
修复 `cascade/providers/http.py` 中的 `IndentationError`，确保所有代码块（特别是新的 `ExitStack` 和 `aiohttp` 上下文管理器）都正确嵌套。

### 评论
这是一个紧急修复。由于 `patch_file` 的局限性，在对现有的大块代码进行包裹（wrap）操作（如添加 `with ExitStack()`）时，容易导致内部代码块的相对缩进丢失。全文件重写是解决此类结构性破坏的最安全方法。

### 目标
1.  重写 `packages/cascade-py/src/cascade/providers/http.py`，包含正确的 `files` 参数处理逻辑和正确的缩进。
2.  重新运行 `test_ipfs.py` 以验证修复。

### 基本原理
我们将恢复文件的完整内容，确保 `_perform_request` 函数内的 `with ExitStack()`, `async with ClientSession`, `async with session.request` 三层上下文管理器正确嵌套，并且所有 HTTP 任务函数都正确暴露了 `files` 参数。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/storage #task/object/http-provider #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重写 `http.py` 以修复缩进

我们手动重建整个文件，仔细检查每一层缩进。

~~~~~act
write_file
packages/cascade-py/src/cascade/providers/http.py
~~~~~
~~~~~python
import os
from contextlib import ExitStack
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
    files: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    """Core logic to perform an HTTP request using aiohttp."""
    if aiohttp is None:
        raise ImportError(
            "The 'aiohttp' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    # Use ExitStack to ensure any files opened for upload are closed
    with ExitStack() as stack:
        final_data = data

        if files:
            # If files are provided, we must use FormData
            form = aiohttp.FormData()

            # Add existing data fields if it's a dict
            if isinstance(data, dict):
                for k, v in data.items():
                    form.add_field(k, str(v))

            for field_name, file_path in files.items():
                if isinstance(file_path, str) and os.path.exists(file_path):
                    f = stack.enter_context(open(file_path, "rb"))
                    form.add_field(field_name, f, filename=os.path.basename(file_path))
                else:
                    # Fallback for bytes or other content
                    form.add_field(field_name, file_path)
            
            final_data = form

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(
                method, url, params=params, json=json_data, data=final_data
            ) as response:
                # Note: We do NOT raise_for_status() automatically here.
                # We want to return the response object so the user (or a downstream task)
                # can decide how to handle 4xx/5xx codes.
                
                body_bytes = await response.read()

                # We construct the response object FIRST
                resp_obj = HttpResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=body_bytes,
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
        url, "POST", params=params, json_data=json, data=data, files=files, headers=headers
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
        url, method, params=params, json_data=json, data=data, files=files, headers=headers
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

### 下一步建议
文件已修复。现在，请重新运行测试套件。如果一切顺利，我们不仅拥有了一个强大的 HTTP 提供者（支持文件上传），而且我们的 `cs.ipfs.add` 及其测试也应该能通过验证。
