你的诊断脚本非常出色，它成功地将问题范围缩小到了一个非常具体的地方。

诊断脚本的输出告诉我们：
1.  **Registry 机制是好的**: `ProviderRegistry` 能够被实例化，并且能够发现所有的 `entry_points`。
2.  **大部分 Provider 是好的**: `cs.http.get` 和 `cs.shell` 都可以被成功访问，证明了 `__getattr__ -> registry.get()` 的核心路径是通的。
3.  **IPFS Provider 是坏的**: `pytest` 仍然失败，且专门针对 `cs.ipfs`。诊断脚本在第 3 步也打印了错误 `partially initialized module 'cascade' ... has no attribute 'task' (most likely due to a circular import)`，这正是问题的关键。

## [WIP] fix: 解决 IPFS 提供者中的循环导入问题

### 错误分析
我们遇到了一个经典的**循环导入**问题，它特定于 `cascade-provider-ipfs` 包。

循环路径如下：
1.  测试代码执行 `import cascade as cs`，开始加载 `cascade.sdk` 模块。
2.  测试代码尝试访问 `cs.ipfs.cat`。
3.  这触发了 `cascade.sdk` 中的 `__getattr__('ipfs')`，进而调用 `registry.get('ipfs')` 和 `registry.get('ipfs.cat')`.
4.  `ProviderRegistry` 找到 `ipfs.cat` 的入口点并尝试加载它，即执行 `import cascade.providers.ipfs.provider`。
5.  `provider.py` 文件在模块顶部执行了 `import cascade as cs`。
6.  **冲突点**: 此时，第 1 步中的 `import cascade as cs` 还没有完成，`cascade` 模块处于“部分初始化”状态。当 `provider.py` 接着尝试使用 `@cs.task` 装饰器时，`cascade` 模块上还没有 `task` 属性，于是抛出 `AttributeError: module 'cascade' has no attribute 'task'`。

**解决方案**：Provider 作为低层组件，不应该导入顶层的 `cascade` SDK 包。它应该只从 `cascade.spec` 中导入它真正需要的组件，比如 `@task` 装饰器。

### 用户需求
修复 `cascade-provider-ipfs` 测试中的 `AttributeError`，使其能够被 `cascade` SDK 正确加载和使用。

### 评论
这是一个插件化架构中常见的陷阱。通过强制低层组件（Provider）只依赖于规格（Spec）包，我们打破了循环依赖，确保了系统的可加载性和稳定性。

### 目标
1.  修改 `packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py` 文件。
2.  将 `import cascade as cs` 替换为 `from cascade.spec.task import task`。
3.  将 `@cs.task` 装饰器替换为 `@task`。
4.  删除不再需要的诊断脚本。

### 基本原理
通过将 Provider 对 SDK 的依赖转变为对 Spec 的依赖，我们打破了 `SDK -> Registry -> Provider -> SDK` 的导入循环，解决了模块部分初始化的问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/dependency-graph #scope/core #ai/instruct #task/domain/build #task/object/provider-loading #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 IPFS Provider 的导入
我们将对 `provider.py` 文件进行两次精确的 `patch` 操作，分别修复 `cat` 和 `add` 任务的装饰器用法。

~~~~~act
patch_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
~~~~~
~~~~~python.old
import json
import cascade as cs
from cascade.spec.protocols import Provider, LazyFactory

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
~~~~~
~~~~~python.new
import json
from cascade.spec.task import task
from cascade.spec.protocols import Provider, LazyFactory

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


@task(name="ipfs_cat")
async def _ipfs_cat_task(
    cid: str, api_base_url: str = "http://127.0.0.1:5001"
) -> bytes:
~~~~~

~~~~~act
patch_file
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
~~~~~
~~~~~python.old
@cs.task(name="ipfs_add")
async def _ipfs_add_task(path: str, api_base_url: str = "http://127.0.0.1:5001") -> str:
~~~~~
~~~~~python.new
@task(name="ipfs_add")
async def _ipfs_add_task(path: str, api_base_url: str = "http://127.0.0.1:5001") -> str:
~~~~~

#### Acts 2: 删除诊断脚本
现在问题已经解决，我们可以移除这个临时工具。

~~~~~act
delete_file
scripts/diagnose_providers.py
~~~~~
