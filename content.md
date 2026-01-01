简要回答
当前的包结构存在严重的**循环依赖与层级倒置**问题：`cascade-sdk`（包含核心工具和示例）在物理上是上游包，但其代码（如示例）却依赖于下游包 `cascade-python` 来定义顶层 API（如 `cs.task`）。这种结构导致在开发 `cascade-sdk` 内部代码时，Pyright 无法正确解析由下游定义的 API。

我们将执行**架构倒置重构**：将顶层 API 的定义权从 `cascade-python`（下游元包）下沉到 `cascade-sdk`（核心实现包）。

## 摘要头
## [WIP] refactor(arch): 将顶层 API 定义下沉至 cascade-sdk 以解决循环依赖

### 错误分析
当前架构存在逻辑死锁：
1.  **定义分离**: `cascade` 的核心 API（`run`, `task`, `Param`）定义在 `cascade-python` 中。
2.  **依赖倒置**: `cascade-sdk` 包含了 `examples` 和 `tools`，这些代码**使用**了核心 API。
3.  **循环死结**: `cascade-python` 依赖 `cascade-sdk`（作为元包）。但在开发环境中，Pyright 分析 `cascade-sdk` 时，只能看到该包内部的上下文。由于 `cascade-sdk` 本身没有定义 API（只有空的或缺失的 `__init__.py`），Pyright 认为 `cs.task` 不存在。

**根本原因**: 作为一个包含示例和工具的包，`cascade-sdk` **必须** 自洽地拥有其所需的 API 定义，而不能依赖于下游的打包工件（`cascade-python`）。

### 用户需求
彻底重构包结构，解决 `reportAttributeAccessIssue` 和 `reportMissingImports`，不仅是修复报错，更是要修正架构设计。

### 评论
这不仅是修复类型检查，这是将 `cascade-sdk` 确立为真正的 "SDK Core"，而将 `cascade-python` 降级为 "Distribution Bundle"（发行版捆绑包）。这是 Monorepo 的最佳实践。

### 目标
1.  将 `cascade-python` 中的富 `__init__.py` 逻辑（API 定义）完全迁移至 `cascade-sdk`。
2.  更新 `cascade-sdk` 的依赖，确保它能支持这些 API（例如添加对 `cascade-library` 的依赖）。
3.  将 `cascade-python` 重置为纯粹的命名空间占位符和依赖聚合器。

### 基本原理
通过将 API 定义下沉到依赖树中更基础的节点（`cascade-sdk`），我们确保了：
1.  **自洽性**: `cascade-sdk` 中的代码（如 `llm_openai.py`）引用 `import cascade` 时，解析的是自身包内的 `__init__.py`，其中现在包含了完整的 API 定义。
2.  **无环依赖**: 下游 `cascade-python` 依然可以依赖 `cascade-sdk`，用户安装 `cascade-python` 依然能获得所有功能，但底层的依赖关系理顺了。

---

### Script

#### Acts 1: 更新 cascade-sdk 依赖

由于我们将 API 定义（包括 `cascade.flow` 等）移入 `cascade-sdk`，我们需要确保 `cascade-sdk` 显式声明了对 `cascade-library` 的依赖（因为 `flow` 逻辑在 library 中）。

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph",
  "cascade-application"
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph",
  "cascade-application",
  "cascade-library"
]
~~~~~

#### Acts 2: 迁移 API 定义至 cascade-sdk

这是核心操作。我们将原属于 `cascade-python` 的 `__init__.py` 内容移动到 `cascade-sdk`，并加入之前讨论的动态属性存根。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# This __init__.py makes 'cascade-sdk' the authoritative source of the 'cascade' namespace API.
# It uses pkgutil to extend the path, ensuring compatibility with other cascade-* packages.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, Callable

# --- Lazy Import Mapping ---
# Maps exported names to (module_path, object_name)
_IMPORT_MAP = {
    # Core Specs
    "task": ("cascade.spec.task", "task"),
    "LazyResult": ("cascade.spec.lazy_types", "LazyResult"),
    "Router": ("cascade.spec.routing", "Router"),
    "Jump": ("cascade.spec.jump", "Jump"),
    "resource": ("cascade.spec.resource", "resource"),
    "inject": ("cascade.spec.resource", "inject"),
    "with_constraints": ("cascade.spec.constraint", "with_constraints"),
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.engine", "Engine"),
    "MessageBus": ("cascade.runtime.bus", "MessageBus"),
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.adapters.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.adapters.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.protocols", "Connector"),
    "StateBackend": ("cascade.spec.protocols", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.graph.serialize", "to_json"),
    "from_json": ("cascade.graph.serialize", "from_json"),
    "override_resource": ("cascade.testing", "override_resource"),
    "ControllerTestApp": ("cascade.testing", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}

# --- Type Checking Imports ---
if TYPE_CHECKING:
    from cascade.spec.task import task
    from cascade.spec.lazy_types import LazyResult
    from cascade.spec.routing import Router
    from cascade.spec.jump import Jump
    from cascade.spec.resource import resource, inject
    from cascade.spec.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor
    from cascade.spec.protocols import Connector, StateBackend

    from cascade.graph.serialize import to_json, from_json
    from cascade.testing import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli
    
    # Dynamic Providers Stubs (for static analysis)
    # These are populated at runtime via __getattr__ delegation to the registry
    http: Any
    template: Any

# --- V1.4 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.input import ParamSpec
    from cascade.common.context import get_current_context
    from cascade.common.inputs import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.common.context import get_current_context
    from cascade.common.inputs import _get_env_var

    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name=name)


# --- Global Functions ---


def run(
    target: Union["LazyResult", List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional["Connector"] = None,
    state_backend: Union[str, Callable[[str], "StateBackend"], None] = None,
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


# --- Dynamic Import & Provider Loading ---


def __getattr__(name: str) -> Any:
    # 1. Check if it's a known API member in our lazy map
    if name in _IMPORT_MAP:
        module_path, obj_name = _IMPORT_MAP[name]
        module = __import__(module_path, fromlist=[obj_name])
        return getattr(module, obj_name)

    # 2. Check if it's a dynamic provider (e.g., cs.read.text)
    # This maintains the v1.3 behavior of dynamic provider loading
    try:
        from cascade.providers.registry import registry

        return registry.get(name)
    except (ImportError, AttributeError):
        # Fallthrough to raise the standard AttributeError below
        pass

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

#### Acts 3: 重置 cascade-python 为纯元包

既然 API 定义已经下沉，`cascade-python` 现在只需要作为一个简单的命名空间包存在，它通过依赖 `cascade-sdk` 来获得功能。它的 `__init__.py` 应该只包含命名空间声明。

~~~~~act
write_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python
# This __init__.py makes 'cascade-python' a regular package that claims the 'cascade' namespace.
# The actual API definition has been moved to 'cascade-sdk' (src/cascade/__init__.py).
# This package now serves primarily as a distribution bundle.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
再次运行 Pyright。现在的预期行为是：
1.  Pyright 分析 `llm_openai.py` 时，`import cascade` 会解析到 `cascade-sdk/src/cascade/__init__.py`。
2.  由于该文件现在包含了 `Param`, `Env` 等定义，以及 `http` 的存根，错误应完全消失。
3.  用户安装 `cascade-python` 时，由于它依赖 `cascade-sdk`，且两者共享命名空间，用户体验不变。
