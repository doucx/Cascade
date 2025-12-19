好的，缓存系统的异步化改造和 `IpfsCacheBackend` 的实现已经通过验证。现在我们将这些变更作为一个完整的逻辑单元提交到版本库。

## [COMMIT] feat(storage): 异步缓存协议迁移与 IpfsCacheBackend 实现

### 用户需求
将缓存系统从同步模型迁移到异步模型，以支持不阻塞引擎事件循环的网络后端（如 IPFS 和 Redis），并提供基于 IPFS 的内容寻址缓存后端实现。

### 评论
这是一次关键的架构演进。将 `CacheBackend` 和 `CachePolicy` 升级为异步协议，虽然对现有适配器是“破坏性”的，但它消除了引擎在处理网络 I/O 时的性能瓶颈。新引入的 `IpfsCacheBackend` 展示了 Cascade 如何利用内容寻址技术实现高效的全局数据去重和分布式缓存。

### 目标
提交异步缓存协议、引擎调度器更新、适配器重构以及 `IpfsCacheBackend` 的完整实现和测试修复。

### 基本原理
1.  **架构一致性**: 确保 Engine 内所有涉及外部 I/O 的扩展点都遵循异步契约。
2.  **内容寻址**: `IpfsCacheBackend` 通过 `Key -> CID -> Content` 的映射，实现了逻辑缓存键与物理内容存储的解耦。
3.  **稳健性**: 修复了由于异步化带来的测试时序竞争问题，确保 CI 环境的稳定性。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/runtime #comp/interfaces #comp/docs #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/async-cache #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交缓存系统重构与 IPFS 后端实现

将所有涉及协议修改、引擎更新、适配器重构及测试修复的文件添加到暂存区。

~~~~~act
git_add
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-runtime/src/cascade/adapters/cache/in_memory.py
packages/cascade-runtime/src/cascade/adapters/cache/redis.py
packages/cascade-runtime/src/cascade/adapters/caching/file_existence.py
packages/cascade-provider-ipfs/pyproject.toml
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/cache.py
tests/cascade-runtime/adapters/cache/test_in_memory.py
tests/cascade-runtime/adapters/cache/test_redis_cache.py
tests/cascade-runtime/runtime/test_engine_constraints.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(storage): migrate caching to async protocol and implement IpfsCacheBackend

This commit transitions the caching infrastructure from a synchronous to an asynchronous model to prevent blocking the engine's event loop during network I/O.

Key Changes:
1. **Protocols**: Updated `CacheBackend` and `CachePolicy` in `cascade-interfaces` to use `async` methods.
2. **Engine**: Updated `Engine.run` to `await` cache check and save operations.
3. **Adapters**:
    - Refactored `InMemoryCacheBackend` and `FileExistenceCache` to be async-compatible.
    - Updated `RedisCacheBackend` to use `asyncio.to_thread` for non-blocking calls to the synchronous redis client.
4. **IPFS Backend**: Implemented `IpfsCacheBackend` in `cascade-provider-ipfs`. It maps cache keys to IPFS CIDs via a metadata backend, leveraging content-addressing for storage.
5. **Tests**: Updated cache unit tests to use `pytest-asyncio` and fixed a race condition in the E2E constraint test that was exposed by the timing changes.

This aligns the storage layer with Cascade's reactive philosophy and enables efficient, deduplicated data storage in distributed environments.
~~~~~

### 下一步建议
- **IPFS 垃圾回收 (GC) 策略**: 随着缓存增加，IPFS 节点可能需要清理。可以考虑研究如何结合 `ttl` 在元数据过期时也触发对 IPFS 内容的 `unpin` 操作。
- **阶段 5.3 探索**: 既然数据已经可以通过 IPFS 交换，下一步可以正式开始设计基于 MQTT 广播工单、基于 IPFS 传递代码和数据的“涌现式分布式执行”模型。
