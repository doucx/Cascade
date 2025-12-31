简要回答
这确实是一个典型的循环依赖和路径错误问题。我将重构 `cascade-python` 的 `__init__.py`，采用惰性导入（Lazy Import）模式来彻底解决顶层命名空间污染问题，并修复其中指向 `cascade.spec.*` 的错误引用。

## [WIP] fix(python): 实施 Lazy Import 并修复路径错误

### 错误分析
测试失败 `ImportError` 揭示了两个核心问题：
1.  **路径错误**: `cascade.spec.context` 等模块并不存在。实际上，`context.py`、`internal/inputs.py` 和 `control_flow.py` 等文件位于 `cascade-sdk` 包的根目录（`cascade.*`），而不是 `cascade-spec` 包（`cascade.spec.*`）中。
2.  **副作用过大**: `cascade/__init__.py` 采用了全量静态导入。当测试 `cascade-vm`（底层包）时，由于 Python 的命名空间机制，顶层的 `cascade/__init__.py` 会被执行，进而尝试导入 `cascade.runtime.engine` 等上层依赖，不仅导致了“依赖倒置”般的加载，还因为上述路径错误直接崩溃。

### 用户需求
1.  修复 `ModuleNotFoundError`，纠正错误的导入路径。
2.  净化 `cascade/__init__.py`，实现按需加载（Lazy Import），确保在导入子模块（如 `cascade.vm`）时不会触发 SDK 全家桶的加载。

### 评论
采用 `TYPE_CHECKING` 配合 `__getattr__` 是维护大型 Python SDK 时的最佳实践。它既保留了 IDE 的智能感知（通过 pyi 或类型存根），又保证了运行时的极致轻量化。对于 `cascade-python` 这种作为“门面”的包，这一点尤为重要。

### 目标
1.  重写 `packages/cascade-python/src/cascade/__init__.py`。
2.  建立 `_IMPORT_MAP` 映射表，修正所有指向 `cascade.spec` 但实际位于 `cascade` 根命名空间的模块路径。
3.  将 `Param`、`Env` 等工厂函数的依赖项移至函数内部导入。
4.  合并现有的 Provider 动态加载逻辑与新的 Lazy Import 逻辑。

### 基本原理
通过 `__getattr__` 钩子拦截属性访问，仅在用户真正使用 `cascade.Engine` 或 `cascade.run` 时才导入相关模块。这切断了 `import cascade` 与其子依赖之间的硬连接，使得 `cascade-vm` 等底层包的单元测试可以独立运行，不再受顶层环境干扰。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/sdk #task/object/init-module #task/action/lazy-import #task/state/begin

---

### Script

#### Acts 1: 重构 `cascade/__init__.py`

我们将完全重写入口文件。所有的静态导入将被移入 `if TYPE_CHECKING:` 块，并使用 `_IMPORT_MAP` 来管理运行时导入。同时，修正了 `context`, `internal.inputs`, `control_flow` 的导入路径。

~~~~~act
write_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python
# This __init__.py makes 'cascade-python' a regular package that claims the 'cascade' namespace.
# It uses pkgutil to extend the path, allowing other implicit namespace packages (PEP 420)
# to be discovered in the same namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import sys
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
    "get_current_context": ("cascade.context", "get_current_context"),
    
    # Advanced Flow Control (Corrected paths: cascade.spec.* -> cascade.*)
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    
    # Runtime
    "Engine": ("cascade.runtime.engine", "Engine"),
    "MessageBus": ("cascade.runtime.bus", "MessageBus"),
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
    "sequence": ("cascade.runtime.flow", "sequence"),
    "pipeline": ("cascade.runtime.flow", "pipeline"),
    
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
    from cascade.context import get_current_context
    
    from cascade.control_flow import select_jump, bind
    
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
    from cascade.runtime.flow import sequence, pipeline
    
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor
    from cascade.spec.protocols import Connector, StateBackend
    
    from cascade.graph.serialize import to_json, from_json
    from cascade.testing import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli

# --- V1.4 Factory Functions ---

def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.input import ParamSpec
    from cascade.context import get_current_context
    from cascade.internal.inputs import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.context import get_current_context
    from cascade.internal.inputs import _get_env_var

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

### 下一步建议
这次修改应该解决了 `cascade-vm` 测试中的导入错误。建议用户重新运行测试以验证修复效果。
`pytest packages/cascade-vm/tests/test_vm.py`
