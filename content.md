简要回答
好的，我们开始实施第二部分：统一 Provider API。我们将首先升级 `ProviderRegistry` 以支持命名空间（如 `cs.read.text`），并实现原子化的 I/O Provider。

## [WIP] feat(providers): 引入原子化 IO Provider 与命名空间支持

### 用户需求
用户目前使用 `cs.file("path").read_text()` 这种双重调用的 API，这与其他 Provider 不一致。用户期望使用更扁平、原子化的 API，如 `cs.read.text("path")` 或 `cs.fs.exists("path")`，这要求系统支持嵌套的 Provider 命名空间。

### 评论
为了实现 `cs.read.text` 这样的调用链，我们需要让 `ProviderRegistry` 具备“部分匹配”的能力：当请求 `read` 且不存在直接对应的 Provider 时，应该返回一个能继续解析后续属性（如 `.text`）的命名空间代理对象。同时，我们需要新建 `io.py` 来承载这些新的原子操作。

### 目标
1.  **Core**: 升级 `ProviderRegistry`，使其支持返回 `ProviderNamespace` 代理对象。
2.  **Feature**: 创建 `src/cascade/providers/io.py`，实现 `read.text`, `read.bytes`, `write.text` 等原子 Provider。
3.  **Config**: 更新 `pyproject.toml` 注册新的 entry points。
4.  **Test**: 添加测试验证新 API 的可用性。

### 基本原理
通过在 `ProviderRegistry.get` 中检测前缀匹配（例如请求 `read` 时发现存在 `read.text`），我们可以动态返回一个 `Namespace` 对象。该对象重载了 `__getattr__`，将属性访问拼接成完整的 Provider 名称（`read` + `.text`）后再次回调 Registry，从而实现无限层级的命名空间支持。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/provider #scope/api #ai/instruct #task/domain/core #task/object/provider-namespace #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 升级 `ProviderRegistry` 支持命名空间
修改 `src/cascade/providers/__init__.py`，引入 `ProviderNamespace` 类并更新 `get` 方法的查找逻辑。

~~~~~act
patch_file
src/cascade/providers/__init__.py
~~~~~
~~~~~python
class ProviderRegistry:
    """
    Manages the discovery and loading of Cascade providers.
    """

    _instance = None

    def __init__(self):
        self._providers: Dict[str, LazyFactory] = {}
        self._loaded = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> LazyFactory:
        """
        Retrieves a provider factory by name. Loads from entry points if not yet loaded.
        Raises AttributeError if not found (to conform with __getattr__ semantics).
        """
        if not self._loaded:
            self._discover_entry_points()
            self._loaded = True

        if name not in self._providers:
            raise AttributeError(f"Cascade provider '{name}' not found.")

        return self._providers[name]

    def register(self, name: str, factory: LazyFactory):
~~~~~
~~~~~python
class ProviderNamespace:
    """
    A proxy object to handle nested provider names (e.g. cs.read.text).
    """
    def __init__(self, registry: "ProviderRegistry", prefix: str):
        self._registry = registry
        self._prefix = prefix

    def __getattr__(self, name: str) -> Any:
        full_name = f"{self._prefix}.{name}"
        return self._registry.get(full_name)


class ProviderRegistry:
    """
    Manages the discovery and loading of Cascade providers.
    """

    _instance = None

    def __init__(self):
        self._providers: Dict[str, LazyFactory] = {}
        self._loaded = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> Any:
        """
        Retrieves a provider factory by name. Loads from entry points if not yet loaded.
        Raises AttributeError if not found (to conform with __getattr__ semantics).
        """
        if not self._loaded:
            self._discover_entry_points()
            self._loaded = True

        if name in self._providers:
            return self._providers[name]

        # Check for namespace match (e.g. asking for 'read' when 'read.text' exists)
        prefix = name + "."
        if any(key.startswith(prefix) for key in self._providers):
            return ProviderNamespace(self, name)

        raise AttributeError(f"Cascade provider '{name}' not found.")

    def register(self, name: str, factory: LazyFactory):
~~~~~

#### Acts 2: 实现原子化 IO Provider
创建 `src/cascade/providers/io.py`，定义新的原子任务和对应的 Provider 类。

~~~~~act
write_file
src/cascade/providers/io.py
~~~~~
~~~~~python
import asyncio
import os
from typing import Any, Union
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider

# --- Async IO Tasks ---

@task(name="read_text")
async def _read_text_task(path: str, encoding: str = "utf-8") -> str:
    def blocking_read():
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    return await asyncio.to_thread(blocking_read)

@task(name="read_bytes")
async def _read_bytes_task(path: str) -> bytes:
    def blocking_read():
        with open(path, "rb") as f:
            return f.read()
    return await asyncio.to_thread(blocking_read)

@task(name="write_text")
async def _write_text_task(path: str, content: str, encoding: str = "utf-8") -> None:
    def blocking_write():
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
    await asyncio.to_thread(blocking_write)

@task(name="write_bytes")
async def _write_bytes_task(path: str, content: bytes) -> None:
    def blocking_write():
        with open(path, "wb") as f:
            f.write(content)
    await asyncio.to_thread(blocking_write)

@task(name="fs_exists")
async def _exists_task(path: str) -> bool:
    return await asyncio.to_thread(os.path.exists, path)

# --- Providers ---

class ReadTextProvider(Provider):
    name = "read.text"
    def create_factory(self) -> LazyFactory:
        return _read_text_task

class ReadBytesProvider(Provider):
    name = "read.bytes"
    def create_factory(self) -> LazyFactory:
        return _read_bytes_task

class WriteTextProvider(Provider):
    name = "write.text"
    def create_factory(self) -> LazyFactory:
        return _write_text_task

class WriteBytesProvider(Provider):
    name = "write.bytes"
    def create_factory(self) -> LazyFactory:
        return _write_bytes_task

class FsExistsProvider(Provider):
    name = "fs.exists"
    def create_factory(self) -> LazyFactory:
        return _exists_task
~~~~~

#### Acts 3: 注册新 Provider
修改 `pyproject.toml`，将新的 Provider 注册到 Entry Points。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
lookup = "cascade.providers.config:LookupProvider"

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
lookup = "cascade.providers.config:LookupProvider"
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"

[tool.hatch.build.targets.wheel]
~~~~~

#### Acts 4: 添加 IO Provider 测试
创建 `tests/providers/test_io.py`。

~~~~~act
write_file
tests/providers/test_io.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

@pytest.fixture
def test_file(tmp_path):
    return tmp_path / "test.txt"

@pytest.mark.asyncio
async def test_read_text_provider(test_file):
    test_file.write_text("hello cascade")
    
    # cs.read.text matches "read.text" provider
    lazy = cs.read.text(str(test_file))
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(lazy)
    assert result == "hello cascade"

@pytest.mark.asyncio
async def test_write_text_provider(test_file):
    # cs.write.text matches "write.text" provider
    lazy = cs.write.text(str(test_file), "written by cascade")
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    await engine.run(lazy)
    
    assert test_file.read_text() == "written by cascade"

@pytest.mark.asyncio
async def test_fs_exists_provider(test_file):
    # cs.fs.exists matches "fs.exists" provider
    lazy_true = cs.fs.exists(str(test_file))
    lazy_false = cs.fs.exists(str(test_file) + ".missing")
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    
    test_file.touch()
    assert await engine.run(lazy_true) is True
    assert await engine.run(lazy_false) is False

def test_provider_registry_namespace_resolution():
    """Verify that accessing intermediate namespaces returns a proxy."""
    # This requires the entry points to be loaded. 
    # Since we are in a test env, we might need to rely on the fact that 'cs' import loaded them 
    # or that we registered them via pyproject.toml (if installed in editable mode).
    # If not installed, we can manually register for this unit test.
    
    from cascade.providers import registry, ProviderNamespace
    from cascade.providers.io import ReadTextProvider
    
    # Manual registration to ensure test isolation
    registry.register("read.text", ReadTextProvider().create_factory())
    
    # Access "read" -> should return Namespace
    ns = registry.get("read")
    assert isinstance(ns, ProviderNamespace)
    
    # Access "read.text" -> should return factory
    factory = ns.text
    assert factory.__name__ == "read_text" # Task name from @task
~~~~~

### 下一步建议
测试通过后，我们将执行路线图的下一步：**废弃旧的 `cs.file` 并更新代码库**。这包括删除旧文件并全局替换引用。
