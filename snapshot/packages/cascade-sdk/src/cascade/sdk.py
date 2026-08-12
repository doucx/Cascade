from typing import TYPE_CHECKING, Any

# --- Lazy Import Mapping ---
# Maps exported names to (module_path, object_name)
_IMPORT_MAP = {
    # Core Specs
    "task": ("cascade.spec.dsl.task", "task"),
    "LazyResult": ("cascade.spec.dsl.fluent", "LazyResult"),
    "Router": ("cascade.spec.dsl.routing", "Router"),
    "Jump": ("cascade.spec.dsl.jump", "Jump"),
    "resource": ("cascade.spec.dsl.resources", "resource"),
    "inject": ("cascade.spec.dsl.resources", "inject"),
    "with_constraints": ("cascade.spec.dsl.constraint", "with_constraints"),
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.bus.core", "EventBus"),
    "FeedbackBus": ("cascade.bus.feedback", "FeedbackBus"),
    "Event": ("cascade.bus.events", "Event"),
    "DependencyMissingError": (
        "cascade.execution.graph.errors",
        "DependencyMissingError",
    ),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.execution.graph.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.runtime.interfaces", "Connector"),
    "StateBackend": ("cascade.spec.runtime.interfaces", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.execution.graph.model.serialize", "to_json"),
    "from_json": ("cascade.execution.graph.model.serialize", "from_json"),
    "override_resource": ("cascade.test_utils.helpers", "override_resource"),
    "ControllerTestApp": ("cascade.test_utils.helpers", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
    # App-level entry points
    "run": ("cascade.app", "run"),
    "visualize": ("cascade.app", "visualize"),
    "dry_run": ("cascade.app", "dry_run"),
}

# --- Type Checking Imports ---
if TYPE_CHECKING:
    from cascade.app import dry_run, run, visualize
    from cascade.bus.core import EventBus
    from cascade.bus.events import Event
    from cascade.common.context import get_current_context
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.execution.graph.model.serialize import from_json, to_json
    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.flow import pipeline, sequence
    from cascade.runtime.host.instance import Engine
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import inject, resource
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.task import task
    from cascade.test_utils.helpers import ControllerTestApp, override_resource

    from .control_flow import bind, select_jump
    from .tools.cli import create_cli

    # Dynamic Providers Stubs (for static analysis)
    # These are populated at runtime via __getattr__ delegation to the registry
    http: Any
    template: Any

# --- V1.4 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.common.context import get_current_context
    from cascade.reflection import _get_param_value
    from cascade.spec.dsl.inputs import ParamSpec

    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.common.context import get_current_context
    from cascade.reflection import _get_env_var
    from cascade.spec.dsl.inputs import EnvSpec

    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name=name)


# --- Dynamic Import & Provider Loading ---


def __getattr__(name: str) -> Any:
    # 0. Ignore internal dunder attributes to prevent recursion/side-effects
    if name.startswith("__"):
        raise AttributeError(f"module 'cascade.sdk' has no attribute '{name}'")

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

    raise AttributeError(f"module 'cascade.sdk' has no attribute '{name}'")


# --- for Introspection ---


def __dir__():
    return sorted(set(list(globals().keys()) + list(_IMPORT_MAP.keys())))


# --- Public API Export ---

__all__ = [
    "ControllerTestApp",
    # Exceptions
    "DependencyMissingError",
    "Engine",
    "Env",
    "Event",
    "EventBus",
    "Jump",
    # Types & Classes
    "LazyResult",
    "LocalExecutor",
    "NativeSolver",
    "Param",
    "Router",
    "bind",
    "create_cli",
    "dry_run",
    "from_json",
    # Context (for advanced usage)
    "get_current_context",
    "inject",
    "override_resource",
    "pipeline",
    "resource",
    "run",
    "select_jump",
    # Advanced Flow Control
    "sequence",
    # Core API
    "task",
    # Tools & Utilities
    "to_json",
    "visualize",
    # Policies & Resources
    "with_constraints",
]
