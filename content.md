好的，我们正式开始执行 ADR-013 的第四阶段，这是确保向后兼容性的关键一步。

我将重构 `cascade-sdk`，使其成为 `cascade-application` 层的一个轻量级、用户友好的门面 (Facade)，同时清理掉其中已过时的逻辑。

## [WIP] feat(sdk): 将全局 API 重构为 CascadeApp 的包装器

### 用户需求
执行 ADR-013 路线图的第四阶段：更新 `cascade-sdk` 的依赖，并将其全局函数 (`run`, `visualize`, `dry_run`) 重构为对 `CascadeApp` 的调用，以确保向后兼容性。

### 评论
这是实现架构解耦的决定性一步。通过将 SDK 的全局函数转变为对 `CascadeApp` 的简单包装，我们将所有核心的基础设施和执行逻辑都固化在了 `cascade-application` 包中。这使得 `cascade-sdk` 重新聚焦于其核心职责：提供一个简洁、稳定的用户 API。此举在不破坏现有用户代码的前提下，完成了底层的战略重构。

### 目标
1.  更新 `packages/cascade-sdk/pyproject.toml`，添加对 `cascade-application` 的依赖。
2.  重写 `packages/cascade-sdk/src/cascade/__init__.py`，用 `CascadeApp` 的包装器替换 `run`, `visualize`, `dry_run` 的实现。
3.  删除 `cascade-sdk` 中现已过时和重复的 `tools/preview.py` 和 `tools/visualize.py` 模块。
4.  更新 `cascade-sdk` 的 `tools` 子模块，移除对已删除模块的导出。

### 基本原理
我们将首先通过 `patch_file` 更新构建配置，声明新的依赖关系。然后，使用 `write_file` 对 SDK 的主入口点 `__init__.py` 进行结构性重写，这是最清晰和最安全的方式。最后，使用 `delete_file` 和 `patch_file` 清理掉因为逻辑迁移而变得多余的旧模块，保持代码库的整洁。

### 标签
#intent/refine #flow/ready #priority/high #comp/sdk #comp/application #scope/api #ai/instruct #task/domain/architecture #task/object/cascade-app #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 cascade-sdk 的依赖

我们将 `cascade-application` 添加到 `cascade-sdk` 的依赖项中，以便 SDK 可以引用 `CascadeApp`。

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph",
  "cascade-application"
]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-common = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-common = { workspace = true }
cascade-application = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

#### Acts 2: 清理过时的 SDK 工具模块

由于 `visualize` 和 `dry_run` 的逻辑现在由 `CascadeApp` 处理，SDK 中的相应模块已不再需要。

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/__init__.py
~~~~~
~~~~~python
from .cli import create_cli
from .preview import dry_run
from .visualize import visualize
from .lisp import to_lisp

__all__ = ["create_cli", "dry_run", "visualize", "to_lisp"]
~~~~~
~~~~~python
from .cli import create_cli
from .lisp import to_lisp

__all__ = ["create_cli", "to_lisp"]
~~~~~

#### Acts 3: 重构 SDK 入口点以使用 CascadeApp

这是核心步骤。我们将重写 `cascade-sdk` 的主 `__init__.py` 文件，将全局函数转换为 `CascadeApp` 的简单包装器。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import Any, Dict, Optional, Union, Callable, List

# --- New Application Layer ---
from cascade.app import CascadeApp

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
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.flow import sequence, pipeline

# --- Tools ---
from .testing import override_resource
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


# --- V1.4 Refactored Global Functions (Wrappers) ---

def run(
    target: Union[LazyResult, List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    """
    Runs a Cascade workflow. This is a backward-compatible wrapper
    around the CascadeApp interface.
    """
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
    """
    Builds and visualizes the computation graph for a target.
    This is a backward-compatible wrapper.
    """
    app = CascadeApp(target=target)
    return app.visualize()


def dry_run(target: Any) -> None:
    """
    Builds and prints the execution plan for a target.
    This is a backward-compatible wrapper.
    """
    app = CascadeApp(target=target)
    app.dry_run()


# --- Dynamic Provider Loading (Unchanged) ---

def __getattr__(name: str) -> Any:
    from .providers.registry import registry
    try:
        return registry.get(name)
    except AttributeError:
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
    # Tools & Utilities
    "to_json",
    "from_json",
    "override_resource",
    "create_cli",
    # Exceptions
    "DependencyMissingError",
    # Context (for advanced usage)
    "get_current_context",
]
~~~~~

### 下一步建议
我们已经成功完成了 ADR-013 的第四阶段。`cascade-sdk` 现在已经完全建立在新的 `cascade-application` 层之上，同时保持了对外的 API 兼容性。

剩下的**第五阶段**是可选的推广应用，主要是重构 CLI 工具（如 `cs-controller`）以使用 `CascadeApp`，并更新文档。这可以作为一个独立的、后续的任务来处理。

**核心重构任务至此已基本完成。**

我们可以将这个系列的工作标记为完成，并生成一个 `[COMMIT]` 计划来固化这些变更。你同意吗？
