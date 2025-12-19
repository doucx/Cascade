我们将创建两个独立的提交。第一个提交包含功能实现（里程碑 5.1），第二个提交包含所有相关的测试和测试修复（里程碑 5.1 的稳定化）。

## [COMMIT] feat(runtime): Implement Redis State and Cache Backends

### 用户需求
实现基于 Redis 的状态后端 (`RedisStateBackend`) 和缓存后端 (`RedisCacheBackend`)，并更新 `cs.run` 入口点以支持通过 URI 字符串（`redis://...`）动态配置这些后端。

### 评论
Redis 后端的引入是 Cascade 从单机工作流向分布式协作系统迈进的关键一步。它提供了工作流中间结果的持久化和可恢复性，为未来的跨进程执行和故障容错奠定了基础。`cs.run` 中的 URI 工厂模式确保了后端配置的灵活性和低耦合性。

### 目标
-   实现 `RedisStateBackend` 和 `RedisCacheBackend`。
-   在 `cascade-runtime` 和 `cascade-py` 中添加 `redis` 可选依赖。
-   重构 `Engine` 构造函数，接受 `state_backend_factory`。
-   在 `cs.run` 中实现 `redis://` URI 解析逻辑，并返回正确的工厂。

### 基本原理
我们使用工厂模式 (`Callable[[str], StateBackend]`) 来解决 `Engine` 需要为每个 Run ID 动态创建新状态后端实例的需求。Redis 后端使用 `pickle` 进行序列化，并使用 Redis Hash 结构来存储 `run_id` 下的任务结果。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/py #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/redis-backend #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加所有修改的文件到暂存区

~~~~~act
git_add
packages/cascade-runtime/pyproject.toml
packages/cascade-py/pyproject.toml
packages/cascade-runtime/src/cascade/adapters/state/redis.py
packages/cascade-runtime/src/cascade/adapters/cache/redis.py
packages/cascade-runtime/src/cascade/adapters/state/__init__.py
packages/cascade-runtime/src/cascade/adapters/cache/__init__.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-py/src/cascade/__init__.py
~~~~~

#### Acts 2: 提交功能实现

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement RedisStateBackend and Engine factory pattern

This commit introduces Redis support for state persistence, marking the first step towards distributed and fault-tolerant execution.

Key Changes:

1.  **Redis Backends:** Implemented `RedisStateBackend` and `RedisCacheBackend` using `redis-py` and `pickle` for serialization.
2.  **Factory Pattern:** Refactored `Engine` to accept a `state_backend_factory` (a callable that produces a StateBackend bound to a `run_id`).
3.  **URI Resolution:** Updated `cs.run` to parse `redis://...` URIs, creating the Redis client and binding it to the state backend factory.
4.  **Dependencies:** Added `redis` as an optional dependency to `cascade-runtime` and `cascade-py`.

This allows users to configure persistence by passing a URI string, e.g., `cs.run(..., state_backend="redis://localhost:6379/0")`.
~~~~~

## [COMMIT] test(runtime): Add and refactor tests for Redis backends

### 用户需求
为 `RedisStateBackend` 和 `RedisCacheBackend` 添加单元测试，并为 `cs.run` 的 URI 解析功能添加集成测试。修复测试文件命名冲突和 Mock 状态问题，以确保测试套件的稳定性和可移植性。

### 评论
该提交将测试代码与主功能实现隔离开来，遵循了功能与测试分离的原则。通过使用有状态的 Mock，我们避免了对外部服务的硬性依赖，并确保了测试的健壮性。

### 目标
-   提交 `test_redis_state.py` 和 `test_redis_cache.py`。
-   提交 `test_state_backends.py` 并修复其中的 Mock 状态逻辑。
-   提交 `__init__.py` 文件以修复包结构和命名冲突。

### 基本原理
所有 Redis 相关的测试现在都使用了一个共享的有状态 Mock 对象，该对象能模拟 `hset` 和 `hget` 等操作，确保了 `pickle` 序列化和反序列化过程的正确性，以及 `cs.run` 入口点逻辑的正确性。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/redis-backend #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加所有测试文件到暂存区

~~~~~act
git_add
tests/cascade-runtime/adapters/state/__init__.py
tests/cascade-runtime/adapters/cache/__init__.py
tests/cascade-runtime/adapters/state/test_redis_state.py
tests/cascade-runtime/adapters/cache/test_redis_cache.py
tests/cascade-py/integration/test_state_backends.py
~~~~~

#### Acts 2: 提交测试实现

~~~~~act
git_commit
~~~~~
~~~~~text
test(runtime): Add robust and portable tests for Redis backends

Introduces comprehensive unit tests for `RedisStateBackend` and `RedisCacheBackend` using mock Redis clients.

Fixes the following issues:
1.  **Naming Conflict:** Renamed test files to ensure unique module names across different subdirectories (e.g., `test_redis.py` -> `test_redis_state.py`).
2.  **Integration Mocking:** Replaced simple `MagicMock` with a stateful mock implementation in `test_state_backends.py`. This mock accurately simulates the `hset` and `hget` cycle of the Redis client, allowing the `Engine`'s full persistence cycle to be verified without requiring a live Redis server.
~~~~~

### 下一步建议
**里程碑 5.1** 已完成并稳定。现在我们有了一个具备持久化状态能力的 Cascade 引擎。

下一步，我们将启动 **里程碑 5.2: 引入 IPFS 作为原生数据层**。这将解决在分布式环境中传递大对象的问题，通过内容寻址和去重，进一步增强 Cascade 的分布式能力。
