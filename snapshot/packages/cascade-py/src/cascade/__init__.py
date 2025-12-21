# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import asyncio
from typing import Any, Dict, Optional, Union, Callable

# Core Specs
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var

# Legacy / Spec Compat
# We keep Param class import removed/hidden as we are overriding it below.
# from cascade.spec.common import Param  <-- Removed

# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> LazyResult:
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
    # Updated to import from the registry module, though .providers init re-exports it.
    # Being explicit is safer.
    from .providers.registry import registry

    try:
        return registry.get(name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# --- Main Run Entrypoint ---
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
):
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )

            # Create a shared client pool
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
    state_backend: Union[str, Callable[[str], StateBackend], None] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        state_backend: A URI string (e.g. "redis://localhost") or a factory function
                       that accepts a run_id and returns a StateBackend.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    sb_factory = _create_state_backend_factory(state_backend)

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(target, params=params))


__all__ = [
    "task",
    "Param",  # Now the factory function
    "Env",  # New factory function
    "run",
    "dry_run",
    "visualize",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "Event",
    "override_resource",
    "DependencyMissingError",
    "get_current_context",  # Exposed for testing/advanced usage
    "create_cli",
]
