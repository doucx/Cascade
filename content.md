好的，船长。我们收到了新的航行指令。

这是一个绝佳的机会来展示 Cascade “提供者组合优于封装”的核心设计哲学。我们将不创建一个庞大的、内置了 IPFS 逻辑的“黑盒”提供者，而是通过组合现有的、原子化的 `cs.http` 和 `cs.task` 积木，来构建出一个透明、可观测且强大的 IPFS 数据层。

我将为你生成启动此里程碑的第一个计划。

## [WIP] feat: 创建 IPFS 提供者包并以组合方式实现 `cat`

### 用户需求
开始实现【里程碑 5.2】，将 IPFS 引入作为 Cascade 的原生数据层。实现过程应遵循“积木组合”的设计原则。

### 评论
这是一个完美的“吃自己的狗粮”的案例。IPFS Kubo 节点通过一个标准的 HTTP RPC API 暴露其功能。因此，我们完全没必要创建一个新的、复杂的、整体式的 `cs.ipfs` 提供者。

取而代之，我们将创建一个 `cascade-provider-ipfs` 包，其中的“提供者”实际上是返回预先组合好的 `LazyResult` 图的工厂函数。这不仅验证了我们核心架构的表达能力，还使得 IPFS 的集成变得极其轻量、透明且易于维护。

### 目标
1.  创建 `packages/cascade-provider-ipfs` 的基本目录结构和 `pyproject.toml` 配置文件。
2.  实现第一个 IPFS 原子任务 `cs.ipfs.cat`，它将通过组合 `cs.http.post` 和一个简单的解析任务来实现。
3.  创建 `IpfsCacheBackend` 的骨架文件，为后续实现奠定基础。

### 基本原理
我们将把对 IPFS 的操作分解为两个原子步骤，并用 Cascade 的原生积木来表达：
1.  **API 调用**: 使用通用的 `cs.http.post` 任务向本地 IPFS 节点的 `/api/v0/cat` 端点发送请求。URL 参数将通过 `cs.template` 动态构建。
2.  **结果解析**: 创建一个简单的、纯函数的 `@cs.task`，它接收 `HttpResponse` 对象并提取其原始 `body` 作为字节流返回。

最终暴露给用户的 `cs.ipfs.cat(...)` 将是一个返回这两步组合图 (`parsing_task(http_task(...))`) 的便捷函数。这种模式是 Cascade 哲学的完美体现。

### 标签
#intent/build #flow/ready #priority/high #scope/api #ai/instruct #task/domain/storage #task/object/ipfs-provider #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建新包的目录结构

首先，我们为 `cascade-provider-ipfs` 创建标准化的包目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-provider-ipfs/src/cascade/providers/ipfs
~~~~~

#### Acts 2: 初始化 `__init__.py` 文件

创建必要的 `__init__.py` 文件，使目录成为合法的 Python 包。

~~~~~act
run_command
~~~~~
~~~~~bash
touch packages/cascade-provider-ipfs/src/cascade/__init__.py
touch packages/cascade-provider-ipfs/src/cascade/providers/__init__.py
touch packages/cascade-provider-ipfs/src/cascade/providers/ipfs/__init__.py
~~~~~

#### Acts 3: 定义 `pyproject.toml`

创建新包的 `pyproject.toml`，定义其元数据、依赖项（`cascade-interfaces` 和 `httpx`）以及关键的 `entry_points`。

~~~~~act
write_file
packages/cascade-provider-ipfs/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-provider-ipfs"
version = "0.1.0"
description = "IPFS providers for the Cascade ecosystem, enabling content-addressed data."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces",
  "httpx"  # For potential future direct use, though not strictly needed by cs.http
]

[project.entry-points."cascade.providers"]
"ipfs.cat" = "cascade.providers.ipfs.provider:IpfsCatProvider"
"ipfs.add" = "cascade.providers.ipfs.provider:IpfsAddProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-py = { path = "../cascade-py", editable = true }
~~~~~

#### Acts 4: 实现组合式的 `cat` 提供者

这是核心部分。我们将创建 `provider.py`，其中 `cs.ipfs.cat` 被实现为一个组合了 `cs.http.post` 和解析任务的工厂函数。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
~~~~~
~~~~~python
from typing import Any
import cascade as cs
from cascade.providers import Provider, LazyFactory
from cascade.providers.http import HttpResponse

# The IPFS RPC API defaults
IPFS_API_BASE_URL = "http://127.0.0.1:5001"


# --- Provider Implementations ---

class IpfsCatProvider(Provider):
    name = "ipfs.cat"

    def create_factory(self) -> LazyFactory:
        # The factory is not a @cs.task, but a regular function that returns one.
        return cat


class IpfsAddProvider(Provider):
    name = "ipfs.add"

    def create_factory(self) -> LazyFactory:
        # The factory is not a @cs.task, but a regular function that returns one.
        return add


# --- Atomic Helper Tasks ---

@cs.task(name="_ipfs_parse_cat_response")
def _parse_cat_response(response: HttpResponse) -> bytes:
    """Parses the raw body from an HttpResponse."""
    if response.status >= 400:
        raise RuntimeError(f"IPFS API Error ({response.status}): {response.text()}")
    return response.body

@cs.task(name="_ipfs_parse_add_response")
def _parse_add_response(response: HttpResponse) -> str:
    """Parses the JSON response from `ipfs add` and returns the CID."""
    if response.status >= 400:
        raise RuntimeError(f"IPFS API Error ({response.status}): {response.text()}")
    # The response is a stream of JSON objects, newline-separated.
    # The last one is the summary for the whole directory/file.
    lines = response.text().strip().split('\n')
    last_line = lines[-1]
    import json
    return json.loads(last_line)['Hash']


# --- User-Facing Factory Functions ---

def cat(cid: str) -> "cs.LazyResult[bytes]":
    """
    Creates a Cascade workflow to retrieve the contents of a file from IPFS.

    This is a composition of `cs.http.post` and a parsing task.
    """
    api_url = f"{IPFS_API_BASE_URL}/api/v0/cat"

    # Step 1: Call the IPFS RPC API
    api_response = cs.http.post(url=api_url, params={"arg": cid})

    # Step 2: Parse the response
    return _parse_cat_response(api_response)


def add(path: str) -> "cs.LazyResult[str]":
    """
    Creates a Cascade workflow to add a local file to IPFS and get its CID.

    This requires `cs.http.post` to support multipart/form-data, which is a
    planned enhancement. For now, this serves as a placeholder for the pattern.
    """
    # NOTE: This will require cs.http.post to be enhanced to support `files=`
    # similar to the `requests` library. This plan doesn't implement that, but
    # lays the groundwork for the pattern.
    api_url = f"{IPFS_API_BASE_URL}/api/v0/add"

    # Step 1: Call the IPFS RPC API with a file upload
    # The conceptual call would look like this:
    # api_response = cs.http.post(url=api_url, files={"file": path})

    # For now, let's create a placeholder that will fail until http is enhanced
    @cs.task
    def _placeholder_add(path: str) -> Any:
        raise NotImplementedError("cs.ipfs.add requires `cs.http.post` to support file uploads.")

    return _placeholder_add(path)
~~~~~

#### Acts 5: 创建 `IpfsCacheBackend` 骨架

最后，我们创建缓存后端的骨架文件。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/cache.py
~~~~~
~~~~~python
from typing import Any, Optional, Dict
from cascade.interfaces.protocols import CacheBackend

class IpfsCacheBackend(CacheBackend):
    """
    A cache backend that stores results in IPFS.

    It uses a fast key-value store (like Redis or in-memory dict) to map
    a task's cache key to a content identifier (CID) in IPFS.
    """
    def __init__(self, metadata_backend: CacheBackend):
        """
        Args:
            metadata_backend: A fast backend (e.g., InMemory, Redis) to store key->CID mappings.
        """
        self._meta_db = metadata_backend

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a CID from metadata and then fetches content from IPFS."""
        cid = self._meta_db.get(key)
        if cid is None:
            return None
        
        # In a real implementation, we would now call a workflow to `cs.ipfs.cat(cid)`
        # and deserialize the result. This requires the engine to be able to run
        # sub-workflows, which is a powerful concept to explore.
        raise NotImplementedError("IPFS cache GET logic requires sub-workflow execution.")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serializes value, adds it to IPFS to get a CID, then stores key->CID mapping."""
        
        # In a real implementation, we would serialize `value`, then call a workflow
        # to `cs.ipfs.add()` the data, get the resulting CID, and then store that
        # in the metadata backend.
        raise NotImplementedError("IPFS cache SET logic requires sub-workflow execution.")
~~~~~

### 下一步建议

我们已经成功地为 IPFS 集成奠定了基础，并以“组合”的方式实现了第一个功能。

1.  **增强 `cs.http.post`**: 下一步的关键是增强 `cascade.providers.http`，使其能够处理 `multipart/form-data` 文件上传。这将解锁 `cs.ipfs.add` 的全部功能。
2.  **实现 `IpfsCacheBackend`**: 一旦 `add` 和 `cat` 功能完备，我们就可以完整地实现 `IpfsCacheBackend` 的 `get` 和 `set` 逻辑，这可能需要引擎支持在策略内部运行子工作流，是一个非常有价值的探索方向。
3.  **编写测试**: 为新的 `cs.ipfs.cat` 提供者编写集成测试，确保它能与本地运行的 IPFS Kubo 节点正确交互。
