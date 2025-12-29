遵循您的架构改进建议，我将把核心协议下沉至 `cascade-spec`，并将 Registry 的实现与单例实例解耦。这涉及创建新的 `manager.py` 来存放 Registry 逻辑，并更新相关定义。

## [WIP] refactor(arch): 将 Provider 协议下沉至 Spec 并解耦 Registry

### 用户需求
1.  **协议下沉**: 将 `Provider` 和 `LazyFactory` 等核心协议从 `cascade-sdk` 移动到 `cascade-spec` 或 `cascade-common`。
2.  **解耦单例**: 将 `ProviderRegistry` 的类实现与其单例实例（`registry`）分离。

### 评论
这是一个非常合理的架构重构。
*   **消除循环依赖风险**: `Provider` 协议是系统扩展的基石，它本质上属于规范层 (`spec`)。放在 `sdk` 中会导致底层库（如 `library`）依赖上层 `sdk` 的定义，虽然 Python 动态特性允许这样做，但这在架构上是不洁的。
*   **提高可测试性**: 将 `ProviderRegistry` 从“强制单例”模式改为“普通类 + 模块级单例实例”模式，使得单元测试可以轻松实例化多个隔离的 Registry，而无需 hack 全局状态。

### 目标
1.  在 `cascade-spec` 中定义 `Provider` 协议。
2.  在 `cascade-sdk` 中创建 `providers/manager.py`，存放 `ProviderRegistry` 和 `ProviderNamespace` 的纯逻辑实现。
3.  重构 `cascade-sdk` 中的 `providers/registry.py`，使其仅作为外观（Facade），负责导出协议（从 spec）和实例化全局 `registry` 对象。

### 基本原理
*   **协议位置**: `cascade-spec` 是所有包的公共依赖基底，放置 `Provider` 协议最合适。
*   **实现位置**: `ProviderRegistry` 涉及插件发现 (`importlib.metadata`)，这是一个运行时行为，适合留在 `cascade-sdk` 中，但应独立于协议定义。
*   **兼容性**: 保持 `cascade.providers.registry` 模块的对外接口 (`Provider`, `registry`) 不变，确保下游代码（如 `cascade-library`）无需修改导入路径。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/sdk #scope/core #ai/instruct #task/domain/architecture #task/object/provider-protocol #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Spec 协议更新
在 `cascade-spec` 中添加 `Provider` 协议定义。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/protocols.py
~~~~~
~~~~~old
class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...


class Connector(Protocol):
~~~~~
~~~~~new
class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...


class Provider(Protocol):
    name: str

    def create_factory(self) -> LazyFactory: ...


class Connector(Protocol):
~~~~~

#### Acts 2: 提取 Registry 实现
创建 `manager.py`，将 `ProviderRegistry` 实现移至此处，并去除单例模式的 `instance()` 方法，改为普通类。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/providers/manager.py
~~~~~
~~~~~python
import sys
import importlib.metadata
from typing import Any, Dict
from cascade.spec.protocols import LazyFactory


class ProviderNamespace:
    def __init__(self, registry: "ProviderRegistry", prefix: str):
        self._registry = registry
        self._prefix = prefix

    def __getattr__(self, name: str) -> Any:
        full_name = f"{self._prefix}.{name}"
        return self._registry.get(full_name)


class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, LazyFactory] = {}
        self._loaded = False

    def get(self, name: str) -> Any:
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
        self._providers[name] = factory

    def _discover_entry_points(self):
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
                # Validate interface (Duck typing check for robustness)
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
~~~~~

#### Acts 3: 重构 Registry 入口
修改 `registry.py`，使其从新位置导入协议和实现，并实例化单例。这样保持了对外 API 的一致性。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/providers/registry.py
~~~~~
~~~~~python
from cascade.spec.protocols import LazyFactory, Provider
from .manager import ProviderRegistry, ProviderNamespace

__all__ = ["LazyFactory", "Provider", "registry", "ProviderRegistry", "ProviderNamespace"]

# Global registry accessor
# Instantiated here to maintain singleton behavior for the module
registry = ProviderRegistry()
~~~~~

### 下一步建议
由于 `cascade-library` 等包通过 `from cascade.providers import Provider` 导入，而 `cascade-sdk` 的 `__init__.py` 从 `registry.py` 导出，上述变更应该是完全向后兼容的。

建议运行测试以确保重构未破坏插件加载机制。
