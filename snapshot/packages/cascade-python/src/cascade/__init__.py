# This __init__.py makes 'cascade-python' a regular package that claims the 'cascade' namespace.
# It uses pkgutil to extend the path, allowing other implicit namespace packages (PEP 420)
# to be discovered in the same namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import Any, Dict, Optional, Union, Callable, List

# --- Core Specs & Legacy Components ---
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints
from cascade.spec.context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from cascade.spec.internal.inputs import _get_param_value, _get_env_var
from cascade.spec.control_flow import select_jump, bind
from cascade.spec.jump import Jump

# --- Runtime (for type hints and exceptions) ---
# Core components explicitly exposed in the public API
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.runtime.flow import sequence, pipeline

# --- Tools ---
from cascade.testing import override_resource, ControllerTestApp
from cascade.sdk.tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.4 Factory Functions ---


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


# --- Global Functions ---


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


# --- Dynamic Provider Loading ---


def __getattr__(name: str) -> Any:
    """
    Dynamically loads providers from the registry when they are accessed as attributes
    on the `cascade` module (e.g., `cs.read.text`).
    """
    from cascade.sdk.providers.registry import registry

    try:
        # Attempt to resolve the name as a provider.
        return registry.get(name)
    except AttributeError:
        # If the provider registry doesn't know the name, we raise the standard
        # module-level AttributeError to maintain expected Python behavior.
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