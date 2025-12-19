简要回答:
分析正确。网络 I/O (IPFS/Redis) 必须是异步的，以避免阻塞引擎的事件循环。我将执行一个包含架构变更的计划：首先将 `CacheBackend` 和 `CachePolicy` 协议迁移为 `async`，然后更新运行时和现有适配器，最后实现基于 `aiohttp` 的 `IpfsCacheBackend`。

## [WIP] feat(storage): 迁移 Cache 协议至异步并实现 IpfsCacheBackend

### 错误分析
无（新功能开发与架构重构）。

### 用户需求
1.  确认 `CacheBackend` 同步接口在处理 IPFS/Redis 等网络 I/O 时的阻塞问题。
2.  将 `CacheBackend` 和 `CachePolicy` 协议升级为异步。
3.  实现 `IpfsCacheBackend`，利用 IPFS 进行内容寻址存储，并使用另一个 `CacheBackend` 存储元数据映射。

### 评论
这是一个“牵一发而动全身”的架构变更，但对于高性能的分布式/网络存储是绝对必要的。如果不做此变更，IPFS 操作将导致 Engine 在等待 HTTP 响应时完全卡死。通过这次重构，我们不仅启用了 IPFS，也为未来全异步的 Redis 操作铺平了道路。

### 目标
1.  修改 `CacheBackend` 和 `CachePolicy` 协议定义为 `async`。
2.  更新 `Engine` 以 `await` 缓存操作。
3.  更新现有实现 (`InMemoryCacheBackend`, `RedisCacheBackend`, `FileExistenceCache`) 适配异步接口。
4.  在 `cascade-provider-ipfs` 中引入 `aiohttp` 依赖。
5.  实现 `IpfsCacheBackend`，支持 `set` (上传+映射) 和 `get` (查找映射+下载)。

### 基本原理
1.  **协议迁移**: 在 `Engine` 这种异步系统中，任何涉及 I/O 的接口都应该是 `async` 的。
2.  **组合模式**: `IpfsCacheBackend` 不直接存储 Key-Value，而是存储 `Key -> CID` (在元数据后端) 和 `CID -> Content` (在 IPFS)。这利用了 IPFS 的去重特性，同时保持了 Key-Value 的语义。
3.  **兼容性**: 对于现有的同步客户端（如 `RedisCacheBackend` 目前可能持有的同步 client），我们将使用 `asyncio.to_thread` 进行非阻塞包装，确保平滑过渡。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/runtime #comp/interfaces #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/cache-backend #task/action/async-migration #task/state/begin

---

### Script

#### Acts 1: 升级接口协议为异步

修改 `CacheBackend` 和 `CachePolicy` 协议，将相关方法改为 `async def`。

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
~~~~~
~~~~~python
class CacheBackend(Protocol):
    """
    Protocol for a storage backend that persists cached results.
    """

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a value by key."""
        ...

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets a value for a key, optionally with a TTL in seconds."""
        ...


class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...
~~~~~
~~~~~python
class CacheBackend(Protocol):
    """
    Protocol for a storage backend that persists cached results.
    """

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves a value by key."""
        ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets a value for a key, optionally with a TTL in seconds."""
        ...


class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...
~~~~~

#### Acts 2: 更新 Engine 以支持异步缓存

修改 `Engine`，在调用 `check` 和 `save` 时使用 `await`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
        )
~~~~~
~~~~~python
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = await node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
        )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                        result_preview=repr(result)[:100],
                    )
                )
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
~~~~~
~~~~~python
                        result_preview=repr(result)[:100],
                    )
                )
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    await node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
~~~~~

#### Acts 3: 更新现有适配器实现

更新 `InMemoryCacheBackend`, `RedisCacheBackend`, 和 `FileExistenceCache` 以匹配新的异步协议。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/cache/in_memory.py
~~~~~
~~~~~python
    def get(self, key: str) -> Optional[Any]:
        if key in self._expiry:
            if time.time() > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = value
        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]
~~~~~
~~~~~python
    async def get(self, key: str) -> Optional[Any]:
        if key in self._expiry:
            if time.time() > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = value
        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/cache/redis.py
~~~~~
~~~~~python
import pickle
from typing import Any, Optional

try:
    import redis
except ImportError:
    redis = None


class RedisCacheBackend:
    """
    A CacheBackend implementation using Redis.
    """

    def __init__(self, client: "redis.Redis", prefix: str = "cascade:cache:"):
        if redis is None:
            raise ImportError("The 'redis' library is required to use RedisCacheBackend.")
        self._client = client
        self._prefix = prefix

    def get(self, key: str) -> Optional[Any]:
        data = self._client.get(self._prefix + key)
        if data is None:
            return None
        return pickle.loads(data)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        data = pickle.dumps(value)
        self._client.set(self._prefix + key, data, ex=ttl)
~~~~~
~~~~~python
import asyncio
import pickle
from typing import Any, Optional

try:
    import redis
except ImportError:
    redis = None


class RedisCacheBackend:
    """
    A CacheBackend implementation using Redis.
    Uses asyncio.to_thread to wrap synchronous redis client calls to ensure
    compatibility with the async Protocol without blocking the loop.
    """

    def __init__(self, client: "redis.Redis", prefix: str = "cascade:cache:"):
        if redis is None:
            raise ImportError("The 'redis' library is required to use RedisCacheBackend.")
        self._client = client
        self._prefix = prefix

    async def get(self, key: str) -> Optional[Any]:
        def _blocking_get():
            data = self._client.get(self._prefix + key)
            if data is None:
                return None
            return pickle.loads(data)

        return await asyncio.to_thread(_blocking_get)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        def _blocking_set():
            data = pickle.dumps(value)
            self._client.set(self._prefix + key, data, ex=ttl)

        await asyncio.to_thread(_blocking_set)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/caching/file_existence.py
~~~~~
~~~~~python
    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass
~~~~~
~~~~~python
    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass
~~~~~

#### Acts 4: 配置 IPFS Provider 依赖

在 `cascade-provider-ipfs` 中添加 `aiohttp`，这是进行异步 HTTP 请求所必需的。

~~~~~act
patch_file
packages/cascade-provider-ipfs/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "aiohttp"
]
~~~~~

#### Acts 5: 实现 IpfsCacheBackend

实现核心逻辑：
1.  **set**: 序列化 -> 异步上传到 IPFS -> 获得 CID -> 异步存储 Key-CID 映射到元数据后端。
2.  **get**: 异步查询 Key -> 获得 CID -> 异步从 IPFS 下载 -> 反序列化。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/cache.py
~~~~~
~~~~~python
import pickle
import json
import logging
from typing import Any, Optional, Union
import aiohttp

from cascade.interfaces.protocols import CacheBackend

logger = logging.getLogger(__name__)

class IpfsCacheBackend(CacheBackend):
    """
    A cache backend that stores results in IPFS via its HTTP RPC API.

    It uses a secondary 'metadata_backend' (like Redis or In-Memory) to map
    application cache keys to IPFS Content Identifiers (CIDs).

    Structure:
       App Key -> Metadata Backend -> CID -> IPFS -> Serialized Data
    """

    def __init__(
        self,
        metadata_backend: CacheBackend,
        ipfs_api_url: str = "http://127.0.0.1:5001",
    ):
        """
        Args:
            metadata_backend: A fast K-V backend to store Key->CID mappings.
            ipfs_api_url: The base URL of the IPFS RPC API (default: local Kubo node).
        """
        self._meta_db = metadata_backend
        self._api_base = ipfs_api_url.rstrip("/")

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves a CID from metadata and then fetches content from IPFS."""
        # 1. Resolve Key -> CID
        cid = await self._meta_db.get(key)
        if not cid:
            return None

        # 2. Fetch Content from IPFS
        try:
            async with aiohttp.ClientSession() as session:
                # ipfs cat <cid>
                url = f"{self._api_base}/api/v0/cat"
                async with session.post(url, params={"arg": cid}) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Failed to fetch CID {cid} from IPFS: {resp.status}"
                        )
                        return None
                    data = await resp.read()

            # 3. Deserialize
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error reading from IPFS cache (key={key}, cid={cid}): {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serializes value, adds it to IPFS to get a CID, then stores key->CID mapping."""
        try:
            # 1. Serialize
            data = pickle.dumps(value)

            # 2. Upload to IPFS
            async with aiohttp.ClientSession() as session:
                url = f"{self._api_base}/api/v0/add"
                # IPFS expects 'file' field in multipart/form-data
                form = aiohttp.FormData()
                form.add_field("file", data)

                async with session.post(url, data=form) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"IPFS add failed: {resp.status} - {text}")
                    
                    # IPFS add returns JSON: {"Name": "...", "Hash": "Qm...", ...}
                    resp_json = await resp.json()
                    cid = resp_json["Hash"]

            # 3. Store Key -> CID Mapping
            # Note: We apply the TTL to the mapping, effectively expiring the cache entry
            # even though the data remains in IPFS (until GC).
            await self._meta_db.set(key, cid, ttl=ttl)

        except Exception as e:
            logger.error(f"Error writing to IPFS cache (key={key}): {e}")
            # We don't raise here to avoid failing the workflow just because caching failed
~~~~~

### 下一步建议
我们已经完成了 Cache 系统的异步化改造并实现了 IPFS 后端。下一步，建议：
1.  **实现 `IpfsCachePolicy`**（如果需要）：目前的实现假设用户手动组合 Backend。如果需要更高级的策略（例如只缓存大于一定大小的文件到 IPFS），可能需要专用的 Policy。
2.  **完善测试**：由于涉及比较大的改动，强烈建议为 `IpfsCacheBackend` 添加单元测试（mock `aiohttp` 和 `metadata_backend`），并更新现有的集成测试以确保 `await` 调用正确。
3.  **继续 Roadmap 5.3**: 既然 IPFS 存储已经就绪，可以开始探索基于“工单”和 IPFS 数据传递的分布式执行模型。
