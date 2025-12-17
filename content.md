好的，我们开始分离 `CacheBackend`。这是第一阶段内核重构的最后一块拼图。

在执行此计划的同时，我将顺便修复你刚才报告的测试错误中关于 `AttributeError: 'MappedLazyResult' object has no attribute 'task'` 的问题，这是一个阻碍性的 Bug，必须立即解决。至于 Pruning 逻辑的回归和测试断言的不匹配，将在后续的 `fix` 计划中统一处理。

## [WIP] refactor(cache): 分离 CacheBackend 协议与修复 Engine 属性错误

### 用户需求
1.  遵循路线图 v2.0，将缓存系统解耦为“策略”与“后端”。引入 `CacheBackend` 协议，用于定义纯粹的键值存储接口。
2.  修复 `Engine.run` 处理 `MappedLazyResult` 时因访问不存在的 `task` 属性而导致的崩溃。

### 评论
当前的缓存实现（如 `FileExistenceCache`）将“由什么决定缓存命中”（文件路径）和“数据存在哪里”（文件系统）混合在了一起。引入 `CacheBackend` 是为了让未来的 `RedisCache`, `S3Cache` 等后端可以被不同的策略复用。

此外，测试暴露出的 `AttributeError` 是 v1.3 引入 `MappedLazyResult` 后，`Engine` 的日志/监控逻辑没有适配造成的。我们需要让 `Engine` 能优雅地识别并获取不同类型目标对象的名称。

### 目标
1.  在 `src/cascade/runtime/protocols.py` 中定义 `CacheBackend` 协议。
2.  在 `src/cascade/adapters/cache` 目录下建立结构，并实现一个基础的 `InMemoryCacheBackend`。
3.  修复 `src/cascade/runtime/engine.py` 中获取 `target_name` 的逻辑，使其兼容 `MappedLazyResult`。

### 基本原理
1.  **协议定义**: `CacheBackend` 将提供标准的 `get(key)` 和 `set(key, value)` 接口。
2.  **适配器模式**: `InMemoryCacheBackend` 将简单地封装一个字典，作为默认的、易于测试的实现。
3.  **鲁棒性增强**: 修改 `Engine.run`，使用 `getattr` 安全地探索 `target` 对象的属性（优先 `task.name`，其次 `factory.name`），确保无论传入的是单个任务还是映射结果，都能正确提取名称用于日志记录。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #comp/interfaces #concept/state #intent/fix
#ai/instruct
#task/domain/architecture #task/object/cache-backend #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: 定义 CacheBackend 协议

首先在协议文件中明确接口定义。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
class Executor(Protocol):
    """
    Protocol for an executor that runs a single task.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes the node's callable with the provided fully-resolved arguments.
        """
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
class Executor(Protocol):
    """
    Protocol for an executor that runs a single task.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes the node's callable with the provided fully-resolved arguments.
        """
        ...


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

#### Acts 2: 创建 Cache 适配器模块与内存实现

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade/adapters/cache
~~~~~

~~~~~act
write_file
src/cascade/adapters/cache/__init__.py
~~~~~
~~~~~
from .in_memory import InMemoryCacheBackend

__all__ = ["InMemoryCacheBackend"]
~~~~~

~~~~~act
write_file
src/cascade/adapters/cache/in_memory.py
~~~~~
~~~~~
from typing import Any, Dict, Optional
import time


class InMemoryCacheBackend:
    """
    A simple in-memory implementation of the CacheBackend protocol.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

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

#### Acts 3: 修复 Engine 中的 AttributeError

修复 `Engine.run` 中获取目标名称的逻辑，使其能处理 `MappedLazyResult`。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        target_name = getattr(target.task, "name", "unknown")

        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )
~~~~~
~~~~~python
    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        
        # Robustly determine target name
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )
~~~~~

### 下一步建议
我们已经完成了第一阶段的主要架构组件定义：`Solver`, `Executor`, `StateBackend`, `CacheBackend` 均已就位，且 `Engine` 已重构为基于 `StateBackend` 运行。

现在的当务之急是**修复回归的测试**。刚才的 `AttributeError` 已经修复，但 `Pruning` 逻辑的回归（Router 分支未正确级联修剪）和 `UpstreamSkipped` 错误码变更仍需处理。

下一个计划应该是 **[FIX] 修复 FlowManager 的修剪逻辑及更新测试套件**。这将确保我们的重构没有破坏核心功能，为后续阶段打下坚实基础。
