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
