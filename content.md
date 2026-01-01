诊断脚本的输出非常清晰，它精确定位了问题所在：
- **`Step 3` 成功了**: `importlib.metadata` 能够找到并加载所有的 provider *实现类*。这意味着 `pyproject.toml` 的 `entry_points` 配置是正确的，并且我们之前添加的 `__init__.py` 文件使得 Python 能够找到这些模块。
- **`Step 4` 失败了**: `ModuleNotFoundError: No module named 'cascade.providers.registry'`。这是根本原因。`cascade.sdk` 中的 `__getattr__` 依赖于 `cascade.providers.registry` 模块来动态发现和加载 provider。但这个模块现在不存在了。

在之前的计划中，我为了消除重复，从 `cascade-sdk` 中删除了 `manager.py` 和 `registry.py`，并错误地假设它们存在于 `cascade-library` 中。`git status` 的输出确认了它们被删除了，而不是被移动。

**解决方案**：将 `manager.py` 和 `registry.py` 恢复到它们正确的、唯一的家——`cascade-library` 包中。

## [WIP] fix: 恢复 Provider 注册表并提交命名空间修复

### 错误分析
诊断脚本明确指出，虽然底层的 `entry_points` 机制可以发现和加载独立的 Provider 类，但负责将它们组织成 `cs.http` 这种可用 API 的核心组件——`ProviderRegistry`——却丢失了。

在之前的重构中，`packages/cascade-sdk/src/cascade/providers/registry.py` 和 `manager.py` 被错误地删除，而不是移动到 `packages/cascade-library` 这个公共基础包中。这导致 `cascade.sdk` 在尝试 `from cascade.providers.registry import registry` 时失败，从而无法初始化 Provider 系统，最终导致了 `AttributeError`。

### 用户需求
恢复被意外删除的 `ProviderRegistry` 模块，并将其放置在 `cascade-library` 包中，以完成整个 Provider 加载机制的修复。

### 评论
这次修复是基于诊断脚本提供的确凿证据，纠正了之前计划中的一个致命疏忽。将 Provider 注册表这个核心基础设施放在 `cascade-library` 中，符合单一事实来源（SSOT）原则，因为所有其他包都依赖它。这也标志着这次复杂的命名空间重构任务的完成。

### 目标
1.  在 `packages/cascade-library/src/cascade/providers/` 目录下恢复 `registry.py` 和 `manager.py`。
2.  将本次和之前所有相关的命名空间修复作为一个原子单元提交到 Git。

### 基本原理
共享的基础设施代码（如 Provider 注册表）必须位于一个被其他组件所依赖的公共包中（在这里是 `cascade-library`）。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/provider-registry #scope/core #ai/instruct #task/domain/build #task/object/provider-loading #task/action/fix #task/state/end

---

### Script

#### Acts 1: 恢复 Provider Registry 模块
我们将 `registry.py` 的内容写回 `packages/cascade-library/src/cascade/providers/`。

~~~~~act
write_file
packages/cascade-library/src/cascade/providers/registry.py
~~~~~
~~~~~python
from cascade.spec.protocols import LazyFactory, Provider
from .manager import ProviderRegistry, ProviderNamespace

__all__ = [
    "LazyFactory",
    "Provider",
    "registry",
    "ProviderRegistry",
    "ProviderNamespace",
]

# Global registry accessor
# Instantiated here to maintain singleton behavior for the module
registry = ProviderRegistry()
~~~~~

#### Acts 2: 恢复 Provider Manager 模块
我们将 `manager.py` 的内容写回 `packages/cascade-library/src/cascade/providers/`。

~~~~~act
write_file
packages/cascade-library/src/cascade/providers/manager.py
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
