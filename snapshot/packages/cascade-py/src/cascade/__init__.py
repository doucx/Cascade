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