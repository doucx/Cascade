简要回答：
好的，我们将启动 Provider 插件架构的实现任务。第一步将建立核心的 Provider 接口和注册机制，并将 `cs.shell` 迁移为首个官方插件。

## [WIP] feat(provider): 建立插件架构并迁移 `cs.shell`

### 用户需求
1.  根据设计文档，实现 `Provider` 接口和插件发现机制（基于 `entry_points`）。
2.  将现有的 `cs.shell` 任务从 `stdlib` 重构为独立的 `ShellProvider`。
3.  修改 `cascade` 的顶层导入逻辑，使其能够动态发现并挂载这些插件，从而保持 `cs.shell` 的 API 不变。

### 评论
这是 `Cascade` 走向生态化的关键一步。通过将功能实现与核心库解耦，我们不仅简化了核心，还为用户扩展 `Cascade` 提供了标准范式。使用 Python 的 `entry_points` 机制是符合 Python 包装最佳实践的选择。此外，在 `__init__.py` 中利用 `__getattr__` 进行懒加载将优化导入性能。

### 目标
1.  创建 `src/cascade/providers` 包，定义 `Provider` 协议和 `Registry`。
2.  实现 `src/cascade/providers/shell.py`。
3.  在 `pyproject.toml` 中注册 `shell` 插件。
4.  重构 `src/cascade/__init__.py` 以支持动态插件加载。
5.  移除旧的 `src/cascade/stdlib.py`。

### 基本原理
我们将遵循“开放/封闭”原则：对扩展开放（通过插件），对修改封闭（核心逻辑）。`ShellProvider` 将作为“金丝雀”实现，验证这套架构的可行性。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/core #comp/build #concept/plugin #scope/api #ai/instruct #task/domain/ecosystem #task/object/provider-system #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 Provider 基础架构

创建 `src/cascade/providers` 目录，并定义 `Provider` 抽象基类和 `Registry` 类。Registry 负责扫描 `entry_points` 并管理已加载的 Provider。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade/providers
~~~~~

~~~~~act
write_file
src/cascade/providers/__init__.py
~~~~~
~~~~~python
import sys
from typing import Callable, Any, Dict, Protocol, Type
import importlib.metadata

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
        """Manually register a factory (mostly for testing or internal use)."""
        self._providers[name] = factory

    def _discover_entry_points(self):
        """Scans the 'cascade.providers' entry point group."""
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group="cascade.providers")
        else:
            entry_points = importlib.metadata.entry_points().get("cascade.providers", [])

        for ep in entry_points:
            try:
                # Load the provider class
                provider_cls = ep.load()
                # Instantiate it
                provider_instance = provider_cls()
                # Validate interface
                if not hasattr(provider_instance, "create_factory") or not hasattr(provider_instance, "name"):
                    print(f"Warning: Plugin {ep.name} does not implement Provider protocol. Skipping.")
                    continue
                
                # Register
                self._providers[provider_instance.name] = provider_instance.create_factory()
            except Exception as e:
                print(f"Error loading plugin {ep.name}: {e}")

# Global registry accessor
registry = ProviderRegistry.instance()
~~~~~

#### Acts 2: 实现 ShellProvider

将原有的 `shell` 任务逻辑迁移到新的 Provider 结构中。注意我们直接复用了 `@task` 装饰器，因为 `Task` 对象本身就符合 `LazyFactory` 协议。

~~~~~act
write_file
src/cascade/providers/shell.py
~~~~~
~~~~~python
import asyncio
from typing import Callable, Any
from cascade.spec.task import task, Task
from cascade.providers import LazyFactory

class ShellProvider:
    name = "shell"

    def create_factory(self) -> LazyFactory:
        return _shell_task

# Define the task logic (moved from stdlib.py)
@task(name="shell")
async def _shell_task(command: str, check: bool = True) -> str:
    """
    Asynchronously executes a shell command and returns its stdout.
    """
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command '{command}' failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{stdout.decode().strip()}\n"
            f"STDERR:\n{stderr.decode().strip()}"
        )

    return stdout.decode().strip()
~~~~~

#### Acts 3: 注册插件

修改 `pyproject.toml`，将新的 `ShellProvider` 注册为 `cascade.providers` 组下的一个 entry point。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"

[tool.hatch.build.targets.wheel]
~~~~~

#### Acts 4: 启用动态加载

修改 `src/cascade/__init__.py`。我们将移除对 `stdlib` 的静态导入，改为定义 `__getattr__` 函数。当用户访问 `cs.shell` 时，它会委托给 `ProviderRegistry` 去查找。

~~~~~act
write_file
src/cascade/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional, List

from .spec.task import task, LazyResult
from .spec.common import Param
from .spec.routing import Router
from .spec.file import File
from .spec.resource import resource, inject
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell", # kept in __all__ for documentation/IDE discovery purposes, though resolved dynamically
]

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


def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus)

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 5: 清理旧文件

删除 `src/cascade/stdlib.py`，因为它已经被迁移。

~~~~~act
delete_file
src/cascade/stdlib.py
~~~~~

#### Acts 6: 修复测试引用

由于 `src/cascade/stdlib.py` 已被删除，我们需要检查并修复任何直接引用该文件的地方。`tests/test_stdlib.py` 的测试用例使用的是 `cs.shell` (通过 `import cascade as cs`)，这应该能通过新的 `__getattr__` 机制正常工作。但是为了稳妥，我们检查一下文件是否存在 direct import。

~~~~~act
check_files_exist
tests/test_stdlib.py
~~~~~

### 下一步建议
1.  **验证机制**: 运行测试。由于 `entry_points` 的生效通常需要安装包（`pip install -e .`），在仅修改源代码的情况下，`importlib.metadata` 可能无法立即找到新添加的 entry point（除非环境支持 editable install 的实时元数据更新）。
2.  **备选方案**: 如果测试因为找不到 entry point 而失败，我们需要在测试环境中手动注册 `ShellProvider` 到 registry，或者确保测试运行在安装后的环境中。
3.  **扩展**: 接下来可以尝试实现 `cs.sql` 或 `cs.http` 的原型。
