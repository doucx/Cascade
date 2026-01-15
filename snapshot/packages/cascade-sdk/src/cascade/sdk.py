from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, Callable

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
}

# --- Type Checking Imports ---
if TYPE_CHECKING:
    from cascade.spec.dsl.task import task
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import resource, inject
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.bus.core import EventBus
    from cascade.bus.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.runtime.interfaces import Connector, StateBackend

    from cascade.execution.graph.model.serialize import to_json, from_json
    from cascade.test_utils.helpers import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli

    # Dynamic Providers Stubs (for static analysis)
    # These are populated at runtime via __getattr__ delegation to the registry
    http: Any
    template: Any

# --- V1.4 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.dsl.inputs import ParamSpec
    from cascade.common.context import get_current_context
    from cascade.reflection import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.dsl.inputs import EnvSpec
    from cascade.common.context import get_current_context
    from cascade.reflection import _get_env_var

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
    # 0. Ignore internal dunder attributes to prevent recursion/side-effects
    if name.startswith("__"):
        raise AttributeError(f"module 'cascade' has no attribute '{name}'")

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

    raise AttributeError(f"module 'cascade' has no attribute '{name}'")


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
    "EventBus",
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
