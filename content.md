Of course. The test failures are extensive and almost all point to the same root cause: the public API exposed by the `cascade-sdk` package is out of sync with the actual refactored locations of the components.

The `_IMPORT_MAP` in `sdk.py` acts as a routing table for lazy-loading, and it's full of outdated paths. The tests, which correctly import from the top-level `cascade` module, are failing because this routing is broken. Additionally, many providers that the tests expect to find (like `cs.shell`, `cs.read`, `cs.sql`) are not even in the map.

I will generate a plan to completely overhaul this file, correcting all the paths and adding the missing provider exports to make the SDK consistent with the rest of the codebase and allow the tests to pass.

## [WIP] fix(sdk): Overhaul SDK exports to align with refactored project structure

### 错误分析

The test suite is experiencing catastrophic failures, with 59 failed tests and 5 errors, almost all stemming from `AttributeError: module 'cascade' has no attribute '...'`. This indicates a critical failure in the public API facade provided by `cascade-sdk`.

The root causes are:
1.  **Outdated Lazy-Loading Map**: The `_IMPORT_MAP` in `packages/cascade-sdk/src/cascade/sdk.py` contains incorrect module paths for core components. For instance, it points to `cascade.runtime.engine` for `Engine`, but the class now resides in `cascade.runtime.host.instance`. This affects `Engine`, `EventBus`, `NativeSolver`, `LocalExecutor`, and `DependencyMissingError`.
2.  **Missing Provider Exports**: Numerous tests for `cascade-library` fail because they expect to import providers directly from the `cascade` module (e.g., `cs.shell`, `cs.read`, `cs.sql`, `cs.http`). These are not listed in the `_IMPORT_MAP`, and the dynamic fallback to the provider registry is either not working as intended or is not the expected access pattern for these tests.

### 用户需求

Fix the SDK's export mechanism (`sdk.py`) to resolve the widespread `AttributeError`s and allow the test suite to pass.

### 评论

This is a critical stabilization fix. An SDK package with a broken public API is unusable. By correcting and completing the export map, we restore the intended developer experience and unblock the entire test suite, ensuring the integrity of the library's functionality.

### 目标

1.  Completely update the `_IMPORT_MAP` in `sdk.py` with the correct, current paths for all core components.
2.  Add entries to the `_IMPORT_MAP` for all standard library providers (`shell`, `read`, `fs`, `sql`, etc.) that the integration tests rely on.
3.  Update the `TYPE_CHECKING` block to match the new, correct paths for improved static analysis and IDE support.
4.  Ensure the `__all__` list is comprehensive and includes all newly exported providers.

### 基本原理

We will perform a single, atomic `write_file` operation on `packages/cascade-sdk/src/cascade/sdk.py`. This is the most robust approach to ensure all outdated paths are corrected and all new provider exports are added simultaneously. By explicitly mapping the providers, we make the public API clear and deterministic, satisfying the expectations of the test suite.

### 标签

#intent/fix #flow/ready #priority/critical #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/testing #task/object/sdk-exports #task/action/refactor #task-state/continue

---

### Script

#### Acts 1: Rebuild the SDK Export Map

This single action will replace the entire `sdk.py` file with a corrected version, fixing all known import paths and adding the missing provider exports.

~~~~~act
write_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python
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
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control
    "select_jump": ("cascade.library.flow", "select_jump"),
    "bind": ("cascade.library.flow", "bind"),
    "sequence": ("cascade.library.flow", "sequence"),
    "pipeline": ("cascade.library.flow", "pipeline"),
    "subflow": ("cascade.library.flow", "subflow"),
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.errors", "DependencyMissingError"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.runtime.kernel.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.protocols", "Connector"),
    "StateBackend": ("cascade.spec.protocols", "StateBackend"),
    # Standard Library Providers
    "shell": ("cascade.library.providers.shell", "shell"),
    "read": ("cascade.library.providers.io", "read"),
    "write": ("cascade.library.providers.io", "write"),
    "fs": ("cascade.library.providers.fs", "fs"),
    "sql": ("cascade.library.providers.sql", "sql"),
    "http": ("cascade.library.providers.http", "http"),
    "template": ("cascade.library.providers.template", "template"),
    "load_yaml": ("cascade.library.providers.config", "load_yaml"),
    "lookup": ("cascade.library.providers.config", "lookup"),
    "dict": ("cascade.library.providers.helpers", "dict"),
    "format": ("cascade.library.providers.helpers", "format"),
    "wait": ("cascade.library.providers.time", "wait"),
    "send": ("cascade.library.providers.signal", "send"),
    "recv": ("cascade.library.providers.signal", "recv"),
    "io": ("cascade.library.providers.s3", "io"),
    "ipfs": ("cascade.provider.ipfs", "ipfs"),
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
    from cascade.common.context import get_current_context

    from cascade.library.flow import select_jump, bind, sequence, pipeline, subflow

    from cascade.runtime.host.instance import Engine
    from cascade.runtime.services.observability.bus import EventBus
    from cascade.runtime.services.observability.events import Event
    from cascade.runtime.errors import DependencyMissingError

    from cascade.runtime.kernel.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.protocols import Connector, StateBackend

    from cascade.graph.serialize import to_json, from_json
    from cascade.testing import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli

    # Library stubs
    from cascade.library.providers.shell import shell
    from cascade.library.providers.io import read, write
    from cascade.library.providers.fs import fs
    from cascade.library.providers.sql import sql
    from cascade.library.providers.http import http
    from cascade.library.providers.template import template
    from cascade.library.providers.config import load_yaml, lookup
    from cascade.library.providers.helpers import dict, format
    from cascade.library.providers.time import wait
    from cascade.library.providers.signal import send, recv
    from cascade.library.providers.s3 import io
    from cascade.provider.ipfs import ipfs


# --- V1.4 Factory Functions ---


def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.input import ParamSpec
    from cascade.common.context import get_current_context
    from cascade.reflection import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
    get_current_context().register(spec)
    return _get_param_value(name=name)


def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
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
        try:
            module = __import__(module_path, fromlist=[obj_name])
            return getattr(module, obj_name)
        except ImportError as e:
            raise ImportError(
                f"Cascade SDK could not lazy-load '{obj_name}' from '{module_path}'. "
                f"Original error: {e}"
            ) from e

    # 2. Check if it's a dynamic provider (legacy support)
    try:
        from cascade.providers.registry import registry

        return registry.get(name)
    except (ImportError, AttributeError):
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
    "subflow",
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
    # Standard Library
    "shell",
    "read",
    "write",
    "fs",
    "sql",
    "http",
    "template",
    "load_yaml",
    "lookup",
    "dict",
    "format",
    "wait",
    "send",
    "recv",
    "io",
    "ipfs",
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
~~~~~

### 下一步建议

This comprehensive update should resolve the vast majority of the test failures. I strongly recommend running the entire test suite again (`pytest`). If any errors persist, they are likely due to more subtle issues than simple import errors, and we can address them next. If the tests pass, we can create a `[COMMIT]` plan to finalize all these fixes.
