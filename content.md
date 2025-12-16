简要回答
执行第一阶段重构：实现输入契约（Specs）、上下文管理（Context）以及内部获取任务，并更新 `cascade.Param` 和 `cascade.Env` 为工厂函数。

## [WIP] feat(core): 实现 v1.3 基础架构与输入契约

### 用户需求
实现 Cascade v1.3 的基础架构，包括 `WorkflowContext`、`InputSpec` 体系以及内部参数获取任务。这是支持同构图和 CLI 解耦的基础。

### 评论
这将解决 `ModuleNotFoundError` 错误，并使 `tests/spec/test_input_context.py` 通过。我们正在将 `Param` 从一个静态的数据结构转变为一个具有副作用（注册上下文）并返回可执行任务（`LazyResult`）的工厂函数。

### 目标
1.  创建 `cascade/spec/input.py` 定义元数据。
2.  创建 `cascade/context.py` 实现上下文管理。
3.  创建 `cascade/internal/inputs.py` 实现 `_get_param_value` 等内部任务。
4.  更新 `cascade/__init__.py` 暴露新的 `Param` 和 `Env` 工厂。

### 基本原理
按照 TDD 计划的第一阶段进行实现。保持 `spec/common.py` 暂时不变（尽管 `Param` 符号在顶层被覆盖），以减少对尚未重构模块的冲击，专注于让新测试通过。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #scope/core #ai/instruct
#task/domain/core #task/object/v1.3-refactor #task/action/impl-phase-1 #task/state/continue

---

### Script

#### Acts 1: 定义 InputSpec 元数据体系
创建 `spec/input.py`，定义参数和环境变量的元数据结构。

~~~~~act
write_file
src/cascade/spec/input.py
~~~~~
~~~~~python
from typing import Any
from dataclasses import dataclass

@dataclass(frozen=True)
class InputSpec:
    """描述一个外部输入契约的元数据基类。"""
    name: str
    default: Any = None
    description: str = ""
    # 注意: 'required' 属性被移除，其逻辑由 'default' 是否存在来隐式定义。
    # 运行时若无 default 且未提供值，则会失败。

@dataclass(frozen=True)
class ParamSpec(InputSpec):
    """描述一个命令行参数的元数据。"""
    type: Any = str  # 用于 CLI 类型转换

@dataclass(frozen=True)
class EnvSpec(InputSpec):
    """描述一个环境变量的元数据。"""
    pass
~~~~~

#### Acts 2: 实现 WorkflowContext
创建 `context.py`，使用 `contextvars` 实现线程安全的上下文管理。

~~~~~act
write_file
src/cascade/context.py
~~~~~
~~~~~python
from contextvars import ContextVar
from typing import Dict, List
from .spec.input import InputSpec

class WorkflowContext:
    def __init__(self):
        self.input_specs: Dict[str, InputSpec] = {}

    def register(self, spec: InputSpec):
        if spec.name in self.input_specs:
            # 在未来可以实现更复杂的合并或警告逻辑
            return
        self.input_specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self.input_specs.values())

# 创建一个全局可访问的上下文变量
_current_context = ContextVar("cascade_workflow_context", default=WorkflowContext())

def get_current_context() -> WorkflowContext:
    """获取当前的 WorkflowContext。"""
    return _current_context.get()
~~~~~

#### Acts 3: 创建内部任务模块
初始化 `internal` 包并实现具体的参数获取任务。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade/internal
touch src/cascade/internal/__init__.py
~~~~~

~~~~~act
write_file
src/cascade/internal/inputs.py
~~~~~
~~~~~python
import os
from typing import Any, Dict, Optional
from cascade.spec.task import task

# 这个任务的职责是从 Engine 提供的参数上下文中获取值。
# 'params_context' 将由 Engine 的参数解析器在运行时注入。
@task(name="_get_param_value")
def _get_param_value(name: str, params_context: Dict[str, Any]) -> Any:
    # 注意：Engine 负责确保 params_context 存在。
    # 如果参数缺失且无默认值，应该在解析阶段或这里报错。
    # 但由于默认值逻辑在 InputSpec 中，这里只负责简单的提取。
    # 实际的默认值回退逻辑可能需要在 Engine/ArgumentResolver 中处理，
    # 或者这个任务本身需要知道 default 值。
    # 简化起见，假设 Engine/Resolver 已经处理了 default 值的注入，
    # 或者 params_context 中包含了所有有效的值。
    
    # 根据 v1.3 设计，InputSpec 持有 default。
    # 如果 ArgumentResolver 没有处理 default，这里就会失败。
    # 为了健壮性，这里的 params_context 应该包含最终决定的值。
    return params_context[name]

# 这个任务的职责是从 OS 环境中获取值。
@task(name="_get_env_var")
def _get_env_var(name: str) -> Optional[str]:
    return os.getenv(name)
~~~~~

#### Acts 4: 更新入口以暴露新工厂
修改 `src/cascade/__init__.py`，实现新的 `Param` 和 `Env` 工厂函数，并整合新模块。

~~~~~act
write_file
src/cascade/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional

# Core Specs
from .spec.task import task
from .spec.lazy_types import LazyResult
from .spec.routing import Router
from .spec.resource import resource, inject
from .spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from .spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var

# Legacy / Spec Compat
# We keep Param class import removed/hidden as we are overriding it below.
# from .spec.common import Param  <-- Removed

# Runtime
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .runtime.exceptions import DependencyMissingError

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---

def Param(name: str, default: Any = None, type: Any = str, description: str = "") -> LazyResult:
    """
    定义一个工作流参数。

    它会向工作流上下文注册其元数据，并返回一个 LazyResult，
    该 LazyResult 在执行时会从用户提供的参数中提取值。
    """
    # 注册 Spec
    # 注意：default=None 作为函数参数默认值，可能与 "无默认值" 混淆。
    # 这里我们假设 None 就是默认值，或者使用 Sentinel 对象。
    # 简单起见，暂用 None。
    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    
    # 返回 LazyResult
    return _get_param_value(name=name)

def Env(name: str, default: Any = None, description: str = "") -> LazyResult:
    """
    定义一个环境变量依赖。
    """
    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    
    return _get_env_var(name=name)


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


# --- Main Run Entrypoint ---

from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer, JsonRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    engine = Engine(bus=event_bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))

__all__ = [
    "task",
    "Param",  # Now the factory function
    "Env",    # New factory function
    "run",
    "dry_run",
    "visualize",
    "cli",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
    "get_current_context", # Exposed for testing/advanced usage
]
~~~~~

### 下一步建议
现在基础架构代码已就位，可以运行第一阶段的测试 `tests/spec/test_input_context.py` 来验证实现是否正确。

如果该测试通过，我们将发现 `tests/graph/test_build.py` 可能会失败，因为它试图构建包含新 `Param` 节点的图，但 `GraphBuilder` 仍保留着处理旧 `node_type="param"` 的逻辑，且可能无法正确处理内部任务。这将引导我们进入第二阶段：图构建的同构化。
