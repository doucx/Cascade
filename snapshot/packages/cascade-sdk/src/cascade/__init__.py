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
    "MessageBus",  # Added MessageBus
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