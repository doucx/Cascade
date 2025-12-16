简要回答：
好的，代码审查发现的这些问题确实影响了代码库的整洁性和逻辑的严密性。

我将生成一个 **[WIP]** 计划，一次性修复这三个具体问题：清理 `http.py` 中的冗余定义、修正 `__init__.py` 中的 `__all__` 导出列表，并简化 `engine.py` 中 `map` 逻辑的死代码。

## [WIP] fix: 修复代码审查中发现的冗余代码和逻辑缺陷

### 用户需求
修复之前代码审查中指出的三个具体技术债务：
1.  `src/cascade/providers/http.py` 中存在重复且废弃的类和函数定义。
2.  `src/cascade/__init__.py` 的 `__all__` 列表中包含了动态加载的 `shell`，违反了 Python 规范。
3.  `src/cascade/runtime/engine.py` 的 `_execute_map_node` 方法中包含永远不会执行的死代码路径。

### 评论
这些虽然主要是清理工作，但对于保持代码库的健康至关重要。特别是 `http.py` 中的重复定义可能会在未来导致严重的混淆。移除死代码和修正导出列表也有助于提高代码的可读性和 IDE 的支持度。

### 目标
1.  重构 `src/cascade/providers/http.py`，移除旧的 `HttpResponse` 类和废弃的 `_http_task` 实现，只保留 `SimpleHttpResponse` 和最新的任务实现。
2.  修改 `src/cascade/__init__.py`，从 `__all__` 中移除 `"shell"`。
3.  修改 `src/cascade/runtime/engine.py`，移除 `if hasattr(factory, "map_item")` 分支。

### 基本原理
*   **消除歧义**: 一个文件中不应有两个同名的函数定义，这依赖于解释器的解析顺序，非常脆弱。
*   **规范性**: `__all__` 应仅包含该模块实际存在的、公开的符号。
*   **代码覆盖率**: 移除死代码可以避免误导阅读者，并防止未来的逻辑错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #comp/runtime #scope/dx #ai/instruct #task/domain/cleanup #task/object/code-review #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 清理 `http.py` 中的冗余代码

我们将移除文件前半部分废弃的 `HttpResponse` 类和未完成的 `_http_task` 函数，保留后半部分正确的 `SimpleHttpResponse` 和最终的 `_http_task` 实现。

~~~~~act
patch_file
src/cascade/providers/http.py
~~~~~
~~~~~python
@dataclass
class HttpResponse:
    """A wrapper around the aiohttp response for a better downstream API."""

    _session: aiohttp.ClientSession
    _response: aiohttp.ClientResponse

    @property
    def status(self) -> int:
        return self._response.status

    async def json(self) -> Any:
        return await self._response.json()

    async def text(self) -> str:
        return await self._response.text()

    async def read(self) -> bytes:
        return await self._response.read()

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status}>"


class HttpProvider:
    name = "http"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required to use the http provider. "
                "Please install it with: pip install cascade-py[http]"
            )
        return _http_task


@task(name="http")
async def _http_task(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    """
    Performs an asynchronous HTTP request.
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(
            method, url, params=params, json=json_data
        ) as response:
            # Ensure the response is fully read or buffered if needed,
            # but for now we pass the raw response to the wrapper.
            # The wrapper will handle reading the body on demand.
            # IMPORTANT: The session will be closed, so the response object
            # must be used within the task that receives it. This is a limitation
            # we might need to address later by e.g. reading the body here.
            # For now, let's keep it simple and assume immediate consumption.

            # Re-evaluating: To make this safe, we should probably return a simple
            # wrapper that already contains the read data. Let's adjust.

            # The session will close, so we need to read the content now.
            # We'll create a more robust wrapper that holds the data.

            # This is a better design:
            final_response = SimpleHttpResponse(
                status=response.status,
                headers=dict(response.headers),
                body=await response.read(),
            )
            response.raise_for_status()
            return final_response


@dataclass
class SimpleHttpResponse:
~~~~~
~~~~~python
class HttpProvider:
    name = "http"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required to use the http provider. "
                "Please install it with: pip install cascade-py[http]"
            )
        return _http_task


@dataclass
class SimpleHttpResponse:
~~~~~

#### Acts 2: 修正 `__init__.py` 的导出列表

移除对 `shell` 的静态导出声明，因为它实际上是动态加载的。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
    "Engine",
    "override_resource",
    "shell",  # kept in __all__ for documentation/IDE discovery purposes, though resolved dynamically
]
~~~~~
~~~~~python
    "Engine",
    "override_resource",
]
~~~~~

#### Acts 3: 简化 `engine.py` 中的 `map` 逻辑

移除 `_execute_map_node` 方法中永远不会执行的 `if` 分支。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
            # Invoke factory to get the LazyResult
            sub_target = (
                factory.map(**kwargs_for_item)
                if hasattr(factory, "map_item")
                else factory(**kwargs_for_item)
            )
            sub_targets.append(sub_target)
~~~~~
~~~~~python
            # Invoke factory to get the LazyResult
            # Task objects implement __call__ to create LazyResult
            sub_target = factory(**kwargs_for_item)
            sub_targets.append(sub_target)
~~~~~

### 下一步建议
执行完此计划后，代码库将变得更加整洁。我们可以运行测试套件（特别是 `test_http.py` 和 `test_map.py`）来确保这些修改没有破坏任何功能。之后，我们可以将这些修复打包提交。
