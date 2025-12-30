好的，信息已收到并完全内化。

你提供的 `cascade/spec/task.py` 和 `cascade/spec/protocols.py` 文件是解开这个谜题的关键。它们 100% 证实了我的核心分析：

1.  **`LazyFactory` 协议**：明确要求实现者提供一个 `.map()` 方法。
2.  **`Task` 类**：`cascade.spec.task.Task` 类是 `@task` 装饰器的产物，它**确实**提供了 `.map()` 方法。
3.  **结论**：任何 `Provider` 的 `create_factory()` 方法都**必须**返回一个 `Task` 实例，才能满足 `LazyFactory` 协议的契约。

当前 `sql.py` 和 `ipfs/provider.py` 的实现返回了普通的 Python 函数，这些函数没有 `.map()` 方法，因此 `pyright` 正确地报告了类型不兼容错误。这是系统 DSL 一致性的一个严重裂痕。

现在，我们将执行之前制定的路线图，生成一个具体的、可执行的计划来修复这个问题。

我将生成一个计划，通过重构 `sql.py` 和 `ipfs/provider.py` 来解决这个核心的架构不一致问题。这将使它们与 `shell.py` 等行为正确的提供者保持一致。

---
## [WIP] refactor: 统一提供者工厂以返回 Task 对象

### 用户需求
系统的核心抽象 `LazyFactory` 与其实现存在严重的不一致。`sql` 和 `ipfs` 等提供者返回的是普通函数，而不是像标准 `@cs.task` 那样返回可组合的 `Task` 对象（即带有 `.map()` 等方法的对象），这破坏了 DSL 的一致性并导致了 `pyright` 类型错误。

### 评论
这是一个至关重要的架构级重构。通过强制所有提供者都返回一个功能完备的 `Task` 对象，我们能确保 Cascade 的 DSL 具备完全一致的行为。用户将能够对 `cs.sql` 或 `cs.ipfs.cat` 等内置提供者使用 `.map()`、`.with_retry()` 等所有策略方法，就像他们对自己定义的任务所做的那样。这将极大地提升开发者体验（DX）和系统的可预测性。

### 目标
1.  重构 `cascade.providers.sql.py`，使其 `SqlProvider` 返回一个 `Task` 对象。
2.  重构 `cascade.providers.ipfs.provider.py`，使其 `IpfsCatProvider` 和 `IpfsAddProvider` 返回 `Task` 对象。
3.  确保修改后的代码符合 `LazyFactory` 协议，从而消除相关的 `pyright` 错误。
4.  接受为了架构一致性而引入的、对 `cs.sql` 和 `cs.ipfs.*` API 的破坏性变更。

### 基本原理
问题的根源在于 `LazyFactory` 协议要求返回的对象必须有 `.map()` 方法，而只有 `@task` 装饰器产生的 `Task` 对象才满足此条件。当前 `sql.py` 和 `ipfs/provider.py` 返回的是普通的 Python 函数，违反了此协议。

我们的策略是：

1.  **遵循正确模式**：以 `cascade.providers.shell.py` 为范本，该提供者正确地返回了一个被 `@task` 装饰的 `_shell_task` 对象。
2.  **原子化任务**：对于 `sql` 和 `ipfs`，我们将它们重构为更底层的、自包含的原子任务。原有的图构建逻辑（如 IPFS 提供者中对 `http.post` 的调用）将被合并到任务函数体内部。这使得任务本身成为一个独立的、可执行的单元。
3.  **API 变更**：为了实现类型正确，我们必须调整 `cs.sql` 的调用签名。`db="res_name"` 的“魔术”将被替换为更明确的 `conn=cs.inject("res_name")`。虽然这是一个破坏性变更，但它使依赖注入机制变得明确和一致，符合 Cascade 的设计哲学。对于 `ipfs`，我们将把 API URL 作为任务的一个参数，以提高其灵活性和可测试性。

此方案将一劳永逸地解决 DSL 的双轨制问题，使所有核心提供者都成为 Cascade 生态中的“一等公民”。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/interfaces #concept/parser #scope/api #scope/dx #ai/brainstorm #task/domain/architecture #task/object/provider-contract #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `sql.py` 以符合 `LazyFactory` 协议

我们将重写 `sql.py`。关键变更：移除 `_sql_factory` 包装函数，将 `_sql_task` 作为核心任务，并更新 `SqlProvider` 直接返回这个 `Task` 对象。这将改变 `cs.sql` 的公共 API。

~~~~~act
write_file
packages/cascade-library/src/cascade/providers/sql.py
~~~~~
~~~~~python
from typing import Any, List, Dict, Optional

try:
    import sqlalchemy
    from sqlalchemy import text
except ImportError:
    sqlalchemy = None

from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
from cascade.providers import LazyFactory, Provider


class SqlProvider(Provider):
    name = "sql"

    def create_factory(self) -> LazyFactory:
        if sqlalchemy is None:
            raise ImportError(
                "The 'sqlalchemy' library is required to use the sql provider. "
                "Please install it with: pip install cascade-py[sql]"
            )
        # Directly return the Task object, satisfying the LazyFactory protocol.
        return _sql_task


@task(name="sql_query")
def _sql_task(
    query: str,
    conn: Any,  # The connection object is now an explicit, injectable argument
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Executes a SQL query using the provided connection.

    Note on API Change:
    The user-facing API is now more explicit. Instead of cs.sql(db="my_db"),
    the call should be cs.sql(conn=cs.inject("my_db"), ...).
    """
    if sqlalchemy is None:
        # This check is redundant if create_factory is called, but good for safety
        raise ImportError("SQLAlchemy is not installed.")

    # 'conn' can be an Engine or a Connection.
    # We use a context manager to ensure proper handling.
    params = params or {}
    stmt = text(query)

    # Check if it's an Engine or Connection by looking for 'connect' method
    if hasattr(conn, "connect"):
        with conn.connect() as active_conn:
            result = active_conn.execute(stmt, params)
            # Try to commit if available (for transaction handling)
            if hasattr(active_conn, "commit"):
                active_conn.commit()

            # Fetch results if it returns rows
            if result.returns_rows:
                # Use mappings() to get dict-like rows
                return [dict(row) for row in result.mappings()]
            return []
    else:
        # Assume it's an already open Connection
        result = conn.execute(stmt, params)
        if hasattr(conn, "commit"):
            conn.commit()

        if result.returns_rows:
            return [dict(row) for row in result.mappings()]
        return []
~~~~~

#### Acts 2: 重构 `ipfs/provider.py` 使其原子化并符合协议

我们将重写 `ipfs/provider.py`。关键变更：移除作为图构建函数的 `cat` 和 `add`，用两个新的、自包含的 `@task` 取代它们，这两个任务内部处理 HTTP 请求和解析。提供者将直接返回这些新的 `Task` 对象。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
~~~~~
~~~~~python
import json
import cascade as cs
from cascade.providers import Provider, LazyFactory

try:
    import aiohttp
except ImportError:
    aiohttp = None


# --- Provider Implementations ---


class IpfsCatProvider(Provider):
    name = "ipfs.cat"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required. Please install it with: pip install aiohttp"
            )
        return _ipfs_cat_task


class IpfsAddProvider(Provider):
    name = "ipfs.add"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required. Please install it with: pip install aiohttp"
            )
        return _ipfs_add_task


# --- Atomic Tasks ---


@cs.task(name="ipfs_cat")
async def _ipfs_cat_task(
    cid: str, api_base_url: str = "http://127.0.0.1:5001"
) -> bytes:
    """
    Fetches content from IPFS for a given CID.
    """
    async with aiohttp.ClientSession() as session:
        url = f"{api_base_url}/api/v0/cat"
        async with session.post(url, params={"arg": cid}) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(f"IPFS API Error ({resp.status}): {body}")
            return await resp.read()


@cs.task(name="ipfs_add")
async def _ipfs_add_task(
    path: str, api_base_url: str = "http://127.0.0.1:5001"
) -> str:
    """
    Adds a local file to IPFS and returns its CID.
    """
    form = aiohttp.FormData()
    # Note: This reads the whole file into memory. For large files, a streaming
    # approach would be better, but this simplifies the task implementation.
    with open(path, "rb") as f:
        form.add_field("file", f)

        async with aiohttp.ClientSession() as session:
            url = f"{api_base_url}/api/v0/add"
            async with session.post(url, data=form) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(f"IPFS API Error ({resp.status}): {body}")

                # The response is a stream of JSON objects, newline-separated.
                # The last one is the summary for the whole directory/file.
                lines = (await resp.text()).strip().split("\n")
                last_line = lines[-1]
                return json.loads(last_line)["Hash"]
~~~~~

### 下一步建议
我们已经对 `sql` 和 `ipfs` 两个提供者进行了根本性的、符合架构原则的重构。

1.  **审查与验证**：在应用这些变更后，应重新运行 `pyright`，确认与 `LazyFactory` 相关的所有错误都已消除。
2.  **更新测试**：由于 `cs.sql` 和 `cs.ipfs.*` 的 API 发生了变更，相关的单元测试和集成测试需要被更新以匹配新的调用签名。例如，`test_sql.py` 中调用 `cs.sql` 的地方需要修改，而 `test_ipfs.py` 中的 `mock_ipfs_server` fixture 需要调整以支持新的 `api_base_url` 参数。
3.  **文档更新**：必须更新所有涉及到 `cs.sql` 和 `cs.ipfs` 的文档和示例代码，以反映新的 API。

如果你同意，我将开始制定更新相关测试文件的计划。
