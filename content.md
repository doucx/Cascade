## [WIP] architect: 创建 cascade-python 聚合包并实施 PEP 420 命名空间

### 摘要
为了彻底解决 `cs.task` 导入失败以及测试中的循环依赖问题，本计划将创建一个新的核心聚合包 `cascade-python`，并对整个 Monorepo 实施 **PEP 420 (隐式命名空间包)** 策略。这将确保 `cascade` 命名空间的初始化逻辑唯一地由 `cascade-python` 控制，消除因 `pkgutil` 初始化顺序不确定性导致的 API 缺失问题。

### 错误分析
当前所有子包（`engine`, `spec`, `sdk` 等）都包含一个仅含 `pkgutil` 样板代码的 `src/cascade/__init__.py`。
在测试环境中，`cascade-engine` 往往先于 `cascade-sdk` 被加载。由于 Python 的导入机制，第一个被加载的 `cascade/__init__.py` 决定了命名空间的初始化。因为 `cascade-engine` 的 `__init__.py` 是空的（只扩展路径），所以 `cascade` 模块加载后不包含任何 API（如 `task`）。
`cascade-sdk` 虽然在其 `__init__.py` 中定义了 API，但由于它不是第一个被加载的，这段代码永远不会执行。

### 用户需求
1.  创建一个 `cascade-python` 包，专门用于聚合和提供常用接口（如 `cs.task`）。
2.  修复测试中 `AttributeError: module 'cascade' has no attribute 'task'` 的问题。
3.  确保解决方案“治本”。

### 评论
这是一个架构级的修复。通过移除所有组件包中的 `src/cascade/__init__.py`（使其成为隐式命名空间），并仅在 `cascade-python` 中保留一个包含逻辑的 `__init__.py`（使其成为显式命名空间/常规包），我们可以利用 Python 的导入优先级规则：**常规包优先于隐式命名空间**。这将强制 Python 总是执行 `cascade-python` 中的初始化代码，无论 `sys.path` 顺序如何。

### 目标
1.  创建 `packages/cascade-python`。
2.  将原 `cascade-sdk` 中的 API 聚合逻辑迁移至 `cascade-python`。
3.  删除所有其他子包中的 `src/cascade/__init__.py`，将其转换为 PEP 420 隐式命名空间包。
4.  更新根目录配置，将 `cascade` 包的源指向 `cascade-python`。

### 基本原理
-   **PEP 420**: 允许没有 `__init__.py` 的目录作为命名空间包。这是 Python 3 的标准。
-   **单一事实来源**: `cascade` 顶层命名空间的 API 导出逻辑只应存在于一个地方。
-   **常规包优先**: 在同名冲突中，Python 会优先加载包含 `__init__.py` 的常规包，这保证了我们的 API 聚合逻辑总是被执行。

### 标签
#intent/architect #flow/ready #priority/high #comp/build #scope/core #task/domain/core #task/object/cascade-python #task/action/restructure #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-python` 包结构
创建新包的目录和配置文件。该包将依赖所有核心组件。

~~~~~act
write_file
packages/cascade-python/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade"
version = "0.1.0"
description = "The official Python SDK for Cascade."
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "cascade-spec",
    "cascade-common",
    "cascade-graph",
    "cascade-engine",
    "cascade-application",
    "cascade-library",
    # Tools included by default
    "cascade-cli-controller",
    "cascade-cli-observer",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-graph = { workspace = true }
cascade-engine = { workspace = true }
cascade-application = { workspace = true }
cascade-library = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
~~~~~

#### Acts 2: 迁移 API 聚合逻辑
将原 `cascade-sdk` 中的 `__init__.py` 内容移动到 `cascade-python`，并保留 `pkgutil` 扩展路径的逻辑（这对兼容隐式命名空间是必须的）。

~~~~~act
write_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python
# This __init__.py makes 'cascade-python' a regular package that claims the 'cascade' namespace.
# It uses pkgutil to extend the path, allowing other implicit namespace packages (PEP 420)
# to be discovered in the same namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import Any, Dict, Optional, Union, Callable, List

# --- Core Specs & Legacy Components ---
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints
from cascade.spec.context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from cascade.spec.internal.inputs import _get_param_value, _get_env_var
from cascade.spec.control_flow import select_jump, bind
from cascade.spec.jump import Jump

# --- Runtime (for type hints and exceptions) ---
# Core components explicitly exposed in the public API
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.runtime.flow import sequence, pipeline

# --- Tools ---
from cascade.testing import override_resource, ControllerTestApp
from cascade.sdk.tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.4 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> LazyResult:
    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> LazyResult:
    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name=name)


# --- Global Functions ---


def run(
    target: Union[LazyResult, List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    from cascade.app import CascadeApp

    app = CascadeApp(
        target=target,
        params=params,
        system_resources=system_resources,
        log_level=log_level,
        log_format=log_format,
        connector=connector,
        state_backend=state_backend,
    )
    return app.run()


def visualize(target: Any) -> str:
    from cascade.app import CascadeApp

    app = CascadeApp(target=target)
    return app.visualize()


def dry_run(target: Any) -> None:
    from cascade.app import CascadeApp

    app = CascadeApp(target=target)
    app.dry_run()


# --- Dynamic Provider Loading ---


def __getattr__(name: str) -> Any:
    """
    Dynamically loads providers from the registry when they are accessed as attributes
    on the `cascade` module (e.g., `cs.read.text`).
    """
    from cascade.sdk.providers.registry import registry

    try:
        # Attempt to resolve the name as a provider.
        return registry.get(name)
    except AttributeError:
        # If the provider registry doesn't know the name, we raise the standard
        # module-level AttributeError to maintain expected Python behavior.
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# --- Public API Export ---

__all__ = [
    # Core API
    "task",
    "Param",
    "Env",
    "run",
    "dry_run",
    "visualize",
    # Advanced Flow Control
    "sequence",
    "pipeline",
    "Router",
    "Jump",
    "select_jump",
    "bind",
    # Policies & Resources
    "with_constraints",
    "resource",
    "inject",
    # Types & Classes
    "LazyResult",
    "Engine",
    "Event",
    "MessageBus",
    "NativeSolver",
    "LocalExecutor",
    # Tools & Utilities
    "to_json",
    "from_json",
    "override_resource",
    "ControllerTestApp",
    "create_cli",
    # Exceptions
    "DependencyMissingError",
    # Context (for advanced usage)
    "get_current_context",
]
~~~~~

#### Acts 3: 实施 PEP 420 - 删除子包的 `__init__.py`
这是最关键的一步。删除所有子包中的 `src/cascade/__init__.py`，使它们成为隐式命名空间包。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -f packages/cascade-application/src/cascade/__init__.py packages/cascade-cli-controller/src/cascade/__init__.py packages/cascade-cli-observer/src/cascade/__init__.py packages/cascade-common/src/cascade/__init__.py packages/cascade-compiler/src/cascade/__init__.py packages/cascade-connector-local/src/cascade/__init__.py packages/cascade-connector-mqtt/src/cascade/__init__.py packages/cascade-engine/src/cascade/__init__.py packages/cascade-graph/src/cascade/__init__.py packages/cascade-library/src/cascade/__init__.py packages/cascade-provider-ipfs/src/cascade/__init__.py packages/cascade-sdk/src/cascade/__init__.py packages/cascade-spec/src/cascade/__init__.py packages/cascade-vm/src/cascade/__init__.py
~~~~~

#### Acts 4: 更新根配置
将根 `pyproject.toml` 中的 `cascade` 包指向新的 `cascade-python` 目录，并更新开发环境依赖。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }
cascade-vm = { workspace = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-compiler",
    "packages/cascade-vm",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-sdk/src/cascade"]
~~~~~
~~~~~toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }
cascade-vm = { workspace = true }
cascade = { path = "packages/cascade-python", editable = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-compiler",
    "packages/cascade-vm",
    "packages/cascade-python",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-python/src/cascade"]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
  # Local workspace packages needed for testing
  "cascade-application",
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-compiler",
  "ruff",
]
~~~~~
~~~~~toml.new
  # Local workspace packages needed for testing
  "cascade-application",
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-compiler",
  "cascade-vm",
  "cascade", # The python sdk
  "ruff",
]
~~~~~

### 下一步建议
我们已经完成了包结构的重组。现在 `cascade` 包 (即 `cascade-python`) 是唯一拥有顶层 `__init__.py` 的包，所有其他包都是隐式命名空间的一部分。这将强制任何 `import cascade` 调用都加载我们的 API 定义。
下一步是运行测试，验证 `AttributeError` 是否已解决。如果仍然有问题，可能需要检查 `cascade-sdk` 内部的相对引用是否因为移动了 `__init__.py` 而断裂。
