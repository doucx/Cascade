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