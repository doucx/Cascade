这是一个实现 **里程碑 5.1: 全局状态总线** 的计划。

我们将在 `cascade-runtime` 中引入 Redis 支持，实现基于 Redis 的状态后端，允许工作流的状态在不同进程甚至机器间共享和持久化。同时，我们将重构 `Engine` 和 `cs.run` 以支持通过工厂模式动态注入状态后端。

## [WIP] feat(runtime): Implement RedisStateBackend and Engine factory pattern

### 用户需求
1.  实现 `RedisStateBackend`，使得工作流的中间结果可以持久化到 Redis，支持跨进程协作和故障恢复。
2.  实现 `RedisCacheBackend`，提供基于 Redis 的缓存存储。
3.  修改 `Engine`，使其接受一个 `state_backend_factory` 而不是固定的类，以便动态配置后端（例如注入 Redis 客户端）。
4.  修改 `cs.run`，支持通过 `state_backend` 参数（接受对象或 URI 字符串如 `redis://...`）来配置运行时的状态后端。

### 评论
这是 "Soma & Memory" 阶段的基石。通过引入 Redis，Cascade 从一个单纯的内存执行引擎进化为一个具备持久化记忆的分布式系统。虽然协议目前保持同步（为了兼容性），但在本地网络环境下 Redis 的性能通常是可以接受的。

### 目标
1.  在 `cascade-runtime` 中添加可选依赖 `redis`。
2.  创建 `cascade.adapters.state.redis.RedisStateBackend`。
3.  创建 `cascade.adapters.cache.redis.RedisCacheBackend`。
4.  更新 `Engine.__init__` 以支持后端工厂。
5.  更新 `cs.run` 以解析 URI 并组装工厂。

### 基本原理
-   **持久化协议**: 使用 `pickle` 序列化结果并存储在 Redis Hash 中 (`cascade:run:{id}:results`)。
-   **工厂模式**: `Engine` 需要为每个 `run_id` 创建一个新的 `StateBackend` 实例。对于 `InMemory`，这很简单；对于 `Redis`，我们需要预先配置好连接池，然后在运行时绑定 `run_id`。工厂函数 `Callable[[str], StateBackend]` 是解决这个问题的优雅方案。
-   **零强制依赖**: Redis 相关代码仅在用户显式请求或安装了 `redis` 库时才会激活。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/redis-backend #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 添加依赖

在 `cascade-runtime` 和 `cascade-py` 中添加 `redis` 相关的可选依赖配置。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-common"
]

[project.optional-dependencies]
csp_solver = ["python-constraint"]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-common"
]

[project.optional-dependencies]
csp_solver = ["python-constraint"]
redis = ["redis"]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
cli = ["typer[all]"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "aiobotocore",
]
~~~~~
~~~~~toml
cli = ["typer[all]"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
redis = ["cascade-runtime[redis]"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "aiobotocore",
  "cascade-runtime[redis]",
]
~~~~~

#### Acts 2: 实现 Redis 适配器

创建 `RedisStateBackend` 和 `RedisCacheBackend`。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/adapters/state/redis.py
~~~~~
~~~~~python
import pickle
from typing import Any, Optional
from cascade.interfaces.protocols import StateBackend

try:
    import redis
except ImportError:
    redis = None


class RedisStateBackend:
    """
    A StateBackend implementation that persists results to Redis.
    """

    def __init__(self, run_id: str, client: "redis.Redis", ttl: int = 86400):
        if redis is None:
            raise ImportError("The 'redis' library is required to use RedisStateBackend.")
        
        self._run_id = run_id
        self._client = client
        self._ttl = ttl
        
        # Keys
        self._results_key = f"cascade:run:{run_id}:results"
        self._skipped_key = f"cascade:run:{run_id}:skipped"

    def put_result(self, node_id: str, result: Any) -> None:
        data = pickle.dumps(result)
        # Use a pipeline to set data and ensure expiry is set
        pipe = self._client.pipeline()
        pipe.hset(self._results_key, node_id, data)
        pipe.expire(self._results_key, self._ttl)
        pipe.execute()

    def get_result(self, node_id: str) -> Optional[Any]:
        data = self._client.hget(self._results_key, node_id)
        if data is None:
            return None
        return pickle.loads(data)

    def has_result(self, node_id: str) -> bool:
        return self._client.hexists(self._results_key, node_id)

    def mark_skipped(self, node_id: str, reason: str) -> None:
        pipe = self._client.pipeline()
        pipe.hset(self._skipped_key, node_id, reason)
        pipe.expire(self._skipped_key, self._ttl)
        pipe.execute()

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = self._client.hget(self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None
~~~~~

~~~~~act
write_file
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

#### Acts 3: 更新 `__init__` 暴露新模块

由于之前的 `__init__.py` 内容简单且我们要更新的内容属于重写，直接使用 `write_file` 以确保一致性。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/adapters/state/__init__.py
~~~~~
~~~~~python
from .in_memory import InMemoryStateBackend

# We don't import RedisStateBackend by default to avoid hard dependency on redis
__all__ = ["InMemoryStateBackend"]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/adapters/cache/__init__.py
~~~~~
~~~~~python
from .in_memory import InMemoryCacheBackend

__all__ = ["InMemoryCacheBackend"]
~~~~~

#### Acts 4: 重构 Engine 支持工厂模式

修改 `Engine` 以支持 `state_backend_factory`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (lambda run_id: InMemoryStateBackend(run_id))
        self.cache_backend = cache_backend
        self.resource_manager = ResourceManager(capacity=system_resources)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Initialize State Backend first (no side effects)
        state_backend = self.state_backend_cls(run_id=run_id)
~~~~~
~~~~~python
        # Initialize State Backend using the factory
        state_backend = self.state_backend_factory(run_id)
~~~~~

#### Acts 5: 更新 `cs.run` 以支持 URI 和配置

更新 `cs.run` 的入口点，引入 URI 解析逻辑。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
def _create_state_backend_factory(backend_spec: Union[str, Callable[[str], StateBackend], None]):
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError("The 'redis' library is required for redis:// backends.")
            
            # Create a shared client pool
            client = redis.from_url(backend_spec)
            
            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)
            
            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    
    Args:
        state_backend: A URI string (e.g. "redis://localhost") or a factory function 
                       that accepts a run_id and returns a StateBackend.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()
    
    sb_factory = _create_state_backend_factory(state_backend)

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~

### 下一步建议
我们已经实现了 Redis 状态后端的基础设施。下一步，我们应该：
1.  **验证**: 编写集成测试，启动一个真实的 Redis（或 mock），验证 `put_result` 和 `get_result` 是否正常工作。
2.  **实现 IPFS**: 既然我们有了持久化状态的能力，接下来的逻辑步骤是实现**里程碑 5.2: 引入 IPFS 作为原生数据层**，以解决大对象传输的问题。
