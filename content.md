Of course. The test failures are extensive and almost all point to the same root cause: the public-facing SDK module (`cascade.sdk`) is failing to correctly locate and export the necessary components. The lazy-loading map (`_IMPORT_MAP`) is outdated and doesn't reflect the actual file structure of the project, causing the `AttributeError` exceptions when tests try to import things like `cs.Engine`.

The errors related to providers like `cs.read`, `cs.shell`, and `cs.http` are also related, as they are loaded through the same `__getattr__` mechanism, which appears to be failing to find them in the provider registry. However, the most immediate and widespread problem is the incorrect paths in the core API map.

I will generate a plan to fix the `_IMPORT_MAP` in `cascade.sdk.py`.

## [WIP] fix: Correct lazy import paths in cascade.sdk

### 错误分析

The vast majority of the 59 test failures are `AttributeError: module 'cascade' has no attribute '...'`. This indicates a critical failure in the public API layer defined in `packages/cascade-sdk/src/cascade/sdk.py`.

This file uses a lazy-loading mechanism via `__getattr__` that relies on an `_IMPORT_MAP` dictionary to resolve module paths. A review of this map shows that many paths are outdated due to recent refactoring. For example:
-   `Engine` is mapped to `cascade.runtime.engine`, but it now resides in `cascade.runtime.host.instance`.
-   `EventBus` is mapped to `cascade.runtime.event_bus`, but its correct path is `cascade.runtime.services.observability.bus`.
-   `DependencyMissingError` is mapped to `cascade.runtime.exceptions`, but it's actually in `cascade.runtime.errors`.

These incorrect paths cause the `__getattr__` function to fail, leading to the widespread `AttributeError`s during testing.

### 用户需求

Fix the `AttributeError`s by correcting the lazy-loading import paths in the main `cascade.sdk` module to match the current project structure. You've also noted that provider-related attributes (`.read`, `.shell`, etc.) should not be added to the explicit exports (`__all__`), as they are handled by a separate plugin mechanism.

### 评论

A stable and correct public API is the most critical contract of an SDK. The current state makes the library completely unusable. Correcting these paths is a high-priority fix that will restore basic functionality and unblock the entire test suite.

### 目标

1.  Identify all incorrect module paths within the `_IMPORT_MAP` dictionary in `packages/cascade-sdk/src/cascade/sdk.py`.
2.  Update these paths to point to the correct locations of the `Engine`, `EventBus`, `Event`, `DependencyMissingError`, `NativeSolver`, and `LocalExecutor` classes.
3.  Ensure the `TYPE_CHECKING` import block also reflects these correct paths for static analysis consistency.

### 基本原理

The solution is to directly patch the `_IMPORT_MAP` dictionary and the corresponding `TYPE_CHECKING` import block in `sdk.py`. By providing the correct module paths, the lazy-loading mechanism will be able to resolve and import the components on demand, satisfying the test suite's import requests and eliminating the `AttributeError`s.

### 标签

#intent/fix #flow/ready #priority/critical #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/testing #task/object/sdk-api #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Correct SDK Import Paths

We will apply two patches to `sdk.py`. The first will fix the lazy-loading map, and the second will update the static type-checking import block to match. This will resolve all the core `AttributeError` issues.

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
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
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.engine", "Engine"),
    "EventBus": ("cascade.runtime.event_bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
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
~~~~~
~~~~~python.new
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
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.errors", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.runtime.kernel.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.protocols", "Connector"),
    "StateBackend": ("cascade.spec.protocols", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.graph.serialize", "to_json"),
    "from_json": ("cascade.graph.serialize", "from_json"),
    "override_resource": ("cascade.testing", "override_resource"),
    "ControllerTestApp": ("cascade.testing", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    from cascade.spec.task import task
    from cascade.spec.lazy_types import LazyResult
    from cascade.spec.routing import Router
    from cascade.spec.jump import Jump
    from cascade.spec.resource import resource, inject
    from cascade.spec.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.runtime.services.observability.bus import EventBus
    from cascade.runtime.services.observability.events import Event
    from cascade.runtime.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.runtime.kernel.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.protocols import Connector, StateBackend

    from cascade.graph.serialize import to_json, from_json
    from cascade.testing import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    from cascade.spec.task import task
    from cascade.spec.lazy_types import LazyResult
    from cascade.spec.routing import Router
    from cascade.spec.jump import Jump
    from cascade.spec.resource import resource, inject
    from cascade.spec.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.runtime.services.observability.bus import EventBus
    from cascade.runtime.services.observability.events import Event
    from cascade.runtime.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.runtime.kernel.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.protocols import Connector, StateBackend

    from cascade.graph.serialize import to_json, from_json
    from cascade.testing import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli
~~~~~

### 下一步建议

The core API import paths have now been corrected. This should resolve the majority of the `AttributeError` failures related to components like `Engine`, `EventBus`, and `DependencyMissingError`.

Please run `pytest` again. We can then analyze any remaining failures, which are likely related to the dynamic provider loading mechanism (`cs.read`, `cs.shell`, etc.).
