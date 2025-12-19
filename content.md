好的，船长。我们已经成功建立并验证了 IPFS 数据层的基础架构。现在我们将这些变更作为一个完整的逻辑单元进行提交。

## [COMMIT] feat(storage): Implement IPFS provider as a composition of HTTP tasks

### 用户需求
实现里程碑 5.2：集成 IPFS 作为 Cascade 的原生数据层，并增强 HTTP 提供者以支持文件上传。

### 评论
这次提交展示了 Cascade 核心哲学的力量：通过组合原子化的积木（HTTP, Task）来构建复杂的功能，而不是增加库的体积。这种模式极大地降低了维护成本并提高了透明度，同时也为后续实现 IPFS 原生缓存铺平了道路。

### 目标
创建一个 Git 提交，记录 IPFS 提供者的实现、HTTP 功能的增强以及相关的测试套件。

### 基本原理
IPFS 是我们“躯体与记忆”愿景的关键，它通过内容寻址解决了分布式系统中的数据一致性和移动问题。将其作为原生提供者引入，并采用“组合优于封装”的原则，不仅验证了 Cascade 的表达能力，也为后续的全局缓存、代码分发和去中心化协作打下了坚实的物质基础。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/interfaces #concept/storage #scope/api #ai/instruct #task/domain/storage #task/object/ipfs-integration #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 提交 IPFS 集成及其依赖增强

我们将所有相关的实现文件、配置文件和测试用例添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-py/src/cascade/providers/http.py
packages/cascade-provider-ipfs/pyproject.toml
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/cache.py
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/__init__.py
packages/cascade-provider-ipfs/src/cascade/providers/__init__.py
packages/cascade-provider-ipfs/src/cascade/__init__.py
pyproject.toml
tests/cascade-py/providers/test_ipfs.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(storage): Implement IPFS provider as a composition of HTTP tasks

Integrates IPFS as a first-class citizen in the Cascade ecosystem by implementing the `cs.ipfs` provider. Following the "Composition Over Encapsulation" principle, IPFS operations are implemented as a orchestration of atomic HTTP tasks.

Key changes:
1.  **`cascade-provider-ipfs` package**: A new lightweight provider package.
2.  **`cs.ipfs.cat(cid)`**: Retrieves content from IPFS by composing `cs.http.post` and a bytes-parsing task.
3.  **`cs.ipfs.add(path)`**: Uploads local files to IPFS by composing `cs.http.post` and a JSON-parsing task.
4.  **`cs.http` Enhancement**: Upgraded the core HTTP provider to support `multipart/form-data` file uploads. Added a `files` parameter to `post`, `put`, and `request` tasks, utilizing `aiohttp.FormData` and `contextlib.ExitStack` for robust resource management.
5.  **Integration Testing**: Added a comprehensive test suite in `tests/cascade-py/providers/test_ipfs.py` that verifies the entire composition flow against a mock IPFS RPC server.

This infrastructure enables location-transparent data handling and serves as the foundation for the upcoming content-addressed global cache.
~~~~~

### 下一步建议

里程碑 5.2 的最后一块拼图是 **IPFS 原生缓存 (`IpfsCacheBackend`)**。

目前，我们面临一个有趣的挑战：`CacheBackend` 的接口在协议定义中是同步的（`get`, `set`），但 IPFS 操作（以及未来的 Redis 操作）本质上是异步的。

我建议下一步：
1.  **升级 `CacheBackend` 协议**: 将其方法修改为 `async`。
2.  **更新引擎**: 修改 `Engine` 调度循环，以便 `await` 缓存检查和保存操作。
3.  **实现 `IpfsCacheBackend`**: 完整实现基于内容寻址的缓存逻辑。

船长，如果你准备好了，我们可以开始对“记忆层”进行异步化改造。
