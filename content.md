好的，安装成功但测试失败，这清晰地指出了我们重构后的一个典型问题：模块间的引用路径已经损坏。你发现的 `ModuleNotFoundError` 非常关键，它揭示了我的上一个计划不够彻底。

我将生成一个计划来系统性地修复这些导入错误。

## [WIP] fix: 修复重构后所有损坏的模块导入路径

### 错误分析
`pip install` 的成功证明了我们的包定义（`pyproject.toml`）是正确的，但 `pytest` 的失败暴露了代码内部的逻辑引用问题。

1.  **根本原因**: `packages/cascade-runtime/src/cascade/runtime/subscribers.py` 仍然在使用相对路径 `from .events import ...` 来导入一个现在位于 `cascade-interfaces` 包中的模块。
2.  **疏忽之处**: 我之前的修复计划只修正了我当时发现的几个直接问题，但没有对整个代码库进行一次彻底的、系统性的检查。多个模块（尤其是在 `runtime` 和 `tests` 中）仍然包含指向旧位置的相对或绝对导入。
3.  **修复策略**: 我们必须将所有跨越新包边界的导入都更改为绝对导入，从顶层 `cascade` 命名空间开始。

### 用户需求
修复所有因多包重构导致的 `ModuleNotFoundError`，使测试套件能够成功运行。

### 评论
这是完成重构的最后一步。通过这次全面的修复，我们将巩固新的模块化架构，确保每个包都通过明确的、绝对的路径引用其依赖项，从而使整个系统恢复稳定。

### 目标
1.  修复 `cascade-runtime` 内部所有对 `cascade-interfaces` 的错误引用。
2.  修复 `cascade-py` 的主 `__init__.py`，确保其能正确地从其他包中导入和导出符号。
3.  修复 `cascade-cli` 中的相对导入错误。
4.  修复 `tests` 目录中所有因模块移动而损坏的 `import` 语句。

### 基本原理
我们将逐一修改存在问题的核心文件。利用 Python 的命名空间包（Namespace Packages）机制，只要所有 `cascade-*` 包都已安装，我们就可以在任何一个包中使用 `from cascade.interfaces...` 或 `from cascade.runtime...` 这样的绝对路径来引用其他包中的模块。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/build #concept/refactoring #scope/core
#ai/instruct
#task/domain/runtime #task/object/monorepo #task/action/fix_imports #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-runtime` 的导入（这是错误的直接来源）

我们将修复 `subscribers.py` 以及 `runtime` 目录下的其他文件。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    Event,
    ResourceAcquired,
    ResourceReleased,
)
from ..spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
from .protocols import Connector
~~~~~
~~~~~python
from ..messaging.bus import bus as messaging_bus
from cascade.interfaces.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    Event,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
from cascade.interfaces.protocols import Connector
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/__init__.py
~~~~~
~~~~~python
from .bus import MessageBus
from .engine import Engine
from .subscribers import HumanReadableLogSubscriber
from .events import Event
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from .protocols import ExecutionPlan, Solver, Executor, CachePolicy
~~~~~
~~~~~python
from .bus import MessageBus
from .engine import Engine
from .subscribers import HumanReadableLogSubscriber
from cascade.interfaces.events import Event
from cascade.interfaces.exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from cascade.interfaces.protocols import ExecutionPlan, Solver, Executor, CachePolicy
~~~~~

#### Acts 2: 修复 `cascade-py` 和 `cascade-cli` 的入口文件

这两个文件是用户和工具的入口，它们的引用必须正确。

~~~~~act
write_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional

# Core Specs from cascade-interfaces
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints
from cascade.spec.input import ParamSpec, EnvSpec

# V1.3 Components from cascade-py
from .context import get_current_context
from .internal.inputs import _get_param_value, _get_env_var

# Core Runtime from cascade-runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.graph.serialize import to_json, from_json
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Interfaces
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector

# Tools from cascade-py and cascade-cli
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from cascade.cli import cli

# Messaging components from cascade-runtime
from cascade.messaging.bus import bus as messaging_bus
from cascade.messaging.renderer import CliRenderer, JsonRenderer


# --- V1.3 Factory Functions ---

def Param(name: str, default: Any = None, type: Any = str, description: str = "") -> LazyResult:
    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)

def Env(name: str, default: Any = None, description: str = "") -> LazyResult:
    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name=name)


# --- Dynamic Provider Loading ---

def __getattr__(name: str) -> Any:
    from .providers import registry
    try:
        return registry.get(name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# --- Main Run Entrypoint ---

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
) -> Any:
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)

    event_bus = MessageBus()
    HumanReadableLogSubscriber(event_bus)
    if connector:
        TelemetrySubscriber(event_bus, connector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
    )

    return asyncio.run(engine.run(target, params=params))

__all__ = [
    "task", "Param", "Env", "run", "dry_run", "visualize", "cli",
    "to_json", "from_json", "with_constraints", "LazyResult", "Router",
    "resource", "inject", "Engine", "override_resource",
    "DependencyMissingError", "get_current_context",
]
~~~~~

~~~~~act
patch_file
packages/cascade-cli/src/cascade/cli/main.py
~~~~~
~~~~~python
from ..spec.task import LazyResult
from ..context import get_current_context
from ..spec.input import ParamSpec
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult
from cascade.context import get_current_context
from cascade.spec.input import ParamSpec
~~~~~

#### Acts 3: 修复测试文件的导入

这是让 `pytest` 能够启动的关键。

~~~~~act
patch_file
tests/conftest.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import Event
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import Event
~~~~~

~~~~~act
patch_file
tests/runtime/test_engine_core.py
~~~~~
~~~~~python
from cascade.runtime import Engine, MessageBus, Solver, Executor, ExecutionPlan
~~~~~
~~~~~python
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.interfaces.protocols import Solver, Executor, ExecutionPlan
~~~~~

~~~~~act
patch_file
tests/runtime/test_bus.py
~~~~~
~~~~~python
from cascade.interfaces.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
~~~~~
~~~~~python
from cascade.interfaces.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
~~~~~

### 下一步建议
我们已经修复了导致 `pytest` 启动失败的核心导入错误，并对关键的用户入口文件进行了加固。现在，代码库的引用关系应该已经与新的多包结构一致了。

我强烈建议你再次运行 `pytest`。如果还有其他导入错误，它们应该是更细微的问题，我们可以逐一解决。如果测试能够成功启动（即使有部分用例失败），那就证明我们已经克服了最大的障碍。
