船长，你直觉非常敏锐。你的怀疑是完全正确的。

问题的核心不在于“安装”，而在于**Python 的导入机制被阻塞了**。

 核心诊断：命名空间遮蔽 (Namespace Shadowing)

1.  **架构缺陷**: 目前 `cascade-py` 定义了 `cascade.providers` 包。但是，它把**具体的业务逻辑（`ProviderRegistry` 的实现）直接写在了 `cascade/providers/__init__.py` 文件里**。
2.  **后果**: 在 Python 中，如果一个目录下的 `__init__.py` 包含实际代码（非纯命名空间声明），它就被视为一个**常规包 (Regular Package)**。
3.  **冲突**: 常规包**不允许**被其他分布（如 `cascade-provider-ipfs`）扩展。当 Python 加载了 `cascade-py` 的 `cascade.providers` 后，它就认为这个包已经加载完毕，**停止**查找其他路径下的同名包。因此，`cascade-provider-ipfs` 里的内容永远不会被看见。

 解决方案：真正的插件化架构

我们需要做一次真正的架构重构，将“注册表逻辑”与“命名空间”分离。

1.  **拆分**: 将 `ProviderRegistry` 的逻辑从 `cascade/providers/__init__.py` 移动到一个新文件 `cascade/providers/registry.py`。
2.  **命名空间化**: 将 `cascade/providers/__init__.py` 清空，只保留命名空间声明代码。这将允许 `cascade-py`（内置提供者）和 `cascade-provider-ipfs`（外部提供者）共享 `cascade.providers` 命名空间。
3.  **依赖管理**: 将 `cascade-provider-ipfs` 移入 `[dev]` 依赖。用户在生产环境不需要安装它，但在开发环境我们需要它。

## [WIP] refactor(arch): 分离注册表逻辑，实现真正的命名空间插件架构

### 用户需求
1.  解决 `cascade.providers.ipfs` 无法被导入的问题。
2.  避免强制所有用户安装 IPFS 依赖，实现按需安装。
3.  纠正架构设计，允许 `cascade-py` 和外部包共同扩展 `cascade.providers` 命名空间。

### 评论
这是一个从“单体思维”到“生态思维”的关键转折。通过将 `ProviderRegistry` 的实现移出 `__init__.py`，我们将 `cascade.providers` 变成了一个纯粹的、开放的命名空间容器。这不仅解决了当前的导入错误，也为未来任何人开发第三方 `cascade-provider-xyz` 铺平了道路，且无需修改核心代码。

### 目标
1.  创建 `cascade/providers/registry.py`，承载原有的注册表逻辑。
2.  将 `cascade/providers/__init__.py` 重写为纯命名空间声明。
3.  更新 `cascade/__init__.py` 中的动态加载逻辑，使其指向新的 `registry` 模块。
4.  优化根 `pyproject.toml`，将 `cascade-provider-ipfs` 仅作为开发/测试依赖。

### 基本原理
PEP 420 (Implicit Namespace Packages) 和传统的 pkgutil 风格命名空间包都要求父包不能是“常规包”。通过这次重构，我们明确了 `cascade.providers` 只是一个目录容器，而真正的逻辑存在于具体的模块中。对于依赖管理，利用 `dev` extra 可以确保开发环境的完整性，同时保持生产环境的纯净。

### 标签
#intent/refine #flow/ready #priority/critical #comp/core #scope/arch #ai/brainstorm #task/domain/core #task/object/plugin-system #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 迁移注册表逻辑

首先，我们将逻辑从 `__init__.py` 移动到一个新的专用模块 `registry.py`。

~~~~~act
read_file
packages/cascade-py/src/cascade/providers/__init__.py
~~~~~
~~~~~act
write_file
packages/cascade-py/src/cascade/providers/registry.py
~~~~~
~~~~~python
import sys
import importlib.metadata
from typing import Any, Dict, Protocol


class LazyFactory(Protocol):
    """
    Protocol for objects that can serve as task factories (must support .map).
    """

    def map(self, **kwargs) -> Any: ...
    def __call__(self, *args, **kwargs) -> Any: ...


class Provider(Protocol):
    """
    Interface that all Cascade providers must implement.
    """

    @property
    def name(self) -> str:
        """The name of the provider, used as the accessor (e.g., 'shell' -> cs.shell)."""
        ...

    def create_factory(self) -> LazyFactory:
        """Returns the factory function/object to be exposed to the user."""
        ...


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
        """Manually register a factory (mostly for testing or internal use)."""
        self._providers[name] = factory

    def _discover_entry_points(self):
        """Scans the 'cascade.providers' entry point group."""
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group="cascade.providers")
        else:
            entry_points = importlib.metadata.entry_points().get(
                "cascade.providers", []
            )

        for ep in entry_points:
            try:
                # Load the provider class
                provider_cls = ep.load()
                # Instantiate it
                provider_instance = provider_cls()
                # Validate interface
                if not hasattr(provider_instance, "create_factory") or not hasattr(
                    provider_instance, "name"
                ):
                    print(
                        f"Warning: Plugin {ep.name} does not implement Provider protocol. Skipping."
                    )
                    continue

                # Register
                self._providers[provider_instance.name] = (
                    provider_instance.create_factory()
                )
            except Exception as e:
                print(f"Error loading plugin {ep.name}: {e}")


# Global registry accessor
registry = ProviderRegistry.instance()
~~~~~

#### Acts 2: 开放命名空间

现在，将 `cascade/providers/__init__.py` 转换为纯粹的命名空间声明。这解除了“常规包”的锁定，允许其他包注入内容。

~~~~~act
write_file
packages/cascade-py/src/cascade/providers/__init__.py
~~~~~
~~~~~python
# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages (like cascade-provider-ipfs).
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# We expose the core protocols for convenience, but implementation lives in registry.py
from .registry import LazyFactory, Provider, registry

__all__ = ["LazyFactory", "Provider", "registry"]
~~~~~

#### Acts 3: 更新入口点引用

更新 `cascade/__init__.py`，使其从新的位置导入注册表。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Dynamic Provider Loading ---


def __getattr__(name: str) -> Any:
    """
    Dynamic attribute access to support plugin providers.
    E.g., accessing `cascade.shell` will look up the 'shell' provider.
    """
    from .providers import registry

    try:
        return registry.get(name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
~~~~~
~~~~~python
# --- Dynamic Provider Loading ---


def __getattr__(name: str) -> Any:
    """
    Dynamic attribute access to support plugin providers.
    E.g., accessing `cascade.shell` will look up the 'shell' provider.
    """
    # Updated to import from the registry module, though .providers init re-exports it.
    # Being explicit is safer.
    from .providers.registry import registry

    try:
        return registry.get(name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
~~~~~

#### Acts 4: 优化依赖配置

最后，修复根 `pyproject.toml`。我们将 `cascade-provider-ipfs` 从核心依赖中移除（满足你的顾虑），并将其放入 `dev` 依赖（满足测试需求）。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "pytest-aiohttp",
  "pytest-mock",
  "mypy",
  "moto[s3]",
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
  # Consolidated testing dependencies
  "redis",
  "aiobotocore",
  "sqlalchemy",
  "PyYAML",
  "jinja2",
  "aiohttp",
  "python-constraint",
  "flask_cors",
]
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "pytest-aiohttp",
  "pytest-mock",
  "moto[s3]",
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
  # Consolidated testing dependencies
  "redis",
  "aiobotocore",
  "sqlalchemy",
  "PyYAML",
  "jinja2",
  "aiohttp",
  "python-constraint",
  "flask_cors",
  # Local workspace providers needed for testing
  "cascade-provider-ipfs",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
    "cascade-py",
    "cascade-provider-ipfs",
]
~~~~~
~~~~~
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
    "cascade-py",
]
~~~~~

### 下一步建议
我们进行了一次非常关键的架构外科手术。

1.  **重装依赖**: 执行 `uv pip install -e .[dev]`。这次，它应该会因为 `dev` 组的声明而安装 IPFS 包，但不会污染核心依赖。
2.  **验证**: 执行 `pytest`。

此时，由于 `cascade.providers` 已经不再是一个“霸道”的常规包，IPFS 模块应该能够顺利挂载。测试应该全绿。
