简要回答
`AttributeError: module 'cascade' has no attribute 'NativeSolver'` 这个错误是由于 `cascade-sdk` 的 `__init__.py` 与 `cascade-application` 之间存在**模块级循环导入依赖**所导致的。

`cascade-sdk` 尝试在顶层导入 `CascadeApp`，而 `CascadeApp` 又依赖于从 `cascade.adapters` 等其他包中导入的组件。这导致在 `cascade` 命名空间完全构建之前，`CascadeApp` 就试图引用尚不存在的子模块，触发了 `cascade-sdk` 的 `__getattr__` 捕获器，进而导致查找 `NativeSolver` 失败并崩溃。

## [WIP] refactor(sdk): 延迟 CascadeApp 导入以修复循环依赖

### 错误分析
1.  **启动流程**：用户执行 `import cascade`，加载 `packages/cascade-sdk/src/cascade/__init__.py`。
2.  **顶层导入**：此 `__init__.py` 文件在模块顶层执行 `from cascade.app import CascadeApp`。
3.  **依赖链**：`cascade.app` (即 `cascade-application` 包) 为了初始化 `CascadeApp`，需要从其他 `cascade` 子包中导入组件，例如 `from cascade.adapters.solvers.native import NativeSolver`。
4.  **查找失败**：在 `cascade.app` 执行其导入时，Python 解释器试图解析 `cascade.adapters`。然而，此时 `cascade` 命名空间还未完全构建，`adapters` 作为子模块尚不可见。
5.  **`__getattr__` 陷阱**：属性查找失败 (`cascade.adapters`) 触发了 `cascade-sdk` 的 `__init__.py` 中定义的 `__getattr__` 函数。这个函数被设计用来动态加载 *Provider*，而不是核心模块。
6.  **崩溃**：`__getattr__` 无法在 Provider 注册表中找到名为 `adapters` 的条目，因此抛出最终的 `AttributeError`。本例中，对`NativeSolver`的查找也走了同样失败的路径。

### 用户需求
修复启动时的 `AttributeError`，确保应用的内部组件能够正确加载。

### 评论
这是一个经典的 Python 架构问题。将实现细节（`CascadeApp`）的导入推迟到函数调用时，是一种有效的解耦策略，可以避免复杂的模块级依赖问题，使包的初始化过程更加健壮和可预测。

### 目标
修改 `packages/cascade-sdk/src/cascade/__init__.py`，将 `CascadeApp` 的导入从模块顶层移至 `run`, `visualize`, 和 `dry_run` 函数内部。

### 基本原理
通过延迟导入，我们打破了模块加载时的循环依赖。当用户调用 `cs.run()` 时，`cascade` 命名空间已经由 Python 的命名空间包机制完全构建好了，此时再在函数内部执行 `from cascade.app import CascadeApp`，解释器就能够成功地找到 `cascade.app` 及其所有下游依赖（如 `cascade.adapters`），从而避免触发 `__getattr__` 陷阱。

### 标签
#intent/fix #intent/refine #flow/ready #priority/critical #comp/sdk #concept/dependency #scope/core #ai/brainstorm #task/domain/core #task/object/import-cycle #task/action/decouple #task/state/begin

---

### Script

#### Acts 1: 延迟 CascadeApp 的导入以解耦

我们将重写 `packages/cascade-sdk/src/cascade/__init__.py`，将 `CascadeApp` 的导入推迟到需要使用它的函数内部。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import Any, Dict, Optional, Union, Callable, List

# --- Core Specs & Legacy Components ---
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints
from .context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var
from .control_flow import select_jump, bind
from cascade.spec.jump import Jump

# --- Runtime (for type hints and exceptions) ---
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.flow import sequence, pipeline

# --- Tools ---
from .testing import override_resource, ControllerTestApp
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.4 Factory Functions (Unchanged) ---


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


# --- V1.4 Refactored Global Functions (Wrappers with deferred import) ---


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


# --- Dynamic Provider Loading (Unchanged) ---


def __getattr__(name: str) -> Any:
    from .providers.registry import registry

    try:
        return registry.get(name)
    except AttributeError:
        # This is the original error that was being hit incorrectly.
        # It's correct for its intended purpose (provider loading).
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
    "MessageBus",  # Added MessageBus
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

### 下一步建议
这次重构应该已经解决了启动崩溃的问题。请重新运行应用或相关测试。如果问题解决，我们可以将这个任务标记为完成并提交。
