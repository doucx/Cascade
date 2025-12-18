我理解了情况。在将项目重构为多包（Monorepo）布局后，Python 的导入路径变得混乱。许多模块仍然在使用相对于旧单包结构的相对导入（例如 `from .spec...`），但在新架构中，这些模块现在位于不同的、独立安装的包中。

错误的核心原因是 `cascade-py` 包中的 `__init__.py` 文件，它作为主入口点，尝试使用无效的相对路径从 `cascade-interfaces` 和 `cascade-runtime` 导入模块，导致整个 `cascade` 命名空间在加载时就已损坏，从而引发了连锁的 `ModuleNotFoundError`。

解决方案是将所有跨包的相对导入修正为绝对导入。在 `uv` 和 Hatch 的工作区（workspace）模式下，所有包都应能通过其绝对路径（`from cascade.spec...`）被正确解析。

我将生成一个计划，使用 `patch_file` 系统地修复这些导入错误。

## [WIP] fix(monorepo): 修复多包重构后损坏的跨包导入路径

### 错误分析
在将项目重构为多包（Monorepo）布局后，`pytest` 在加载测试时因 `ModuleNotFoundError` 而失败。根本原因在于，重构后的各个包（如 `cascade-py`, `cascade-runtime`）内部的 Python 模块仍然在使用旧的相对导入路径（例如 `from .spec...` 或 `from ..graph...`）来引用那些已经被移动到其他包（如 `cascade-interfaces`）中的代码。

在可编辑（editable）安装的工作区模式下，每个包都被独立地添加到 Python 路径中，它们共同构成了 `cascade` 命名空间。因此，包之间的引用**必须**使用绝对导入路径（例如 `from cascade.spec...`），而不是相对路径。当前的相对导入路径在 `cascade-py` 的 `__init__.py` 中首先触发了错误，导致整个 `cascade` 包无法被正确初始化，从而引发了所有测试文件中的连锁导入失败。

### 用户需求
修复因多包重构导致的 `ModuleNotFoundError`，使 `pytest` 能够成功运行。

### 评论
这是一个在代码库架构重构后常见的、关键的修复步骤。将导入路径与新的多包结构对齐，是保证代码库可维护性和功能正确性的基础。这个修复将解锁整个项目的测试和后续开发工作。

### 目标
1.  系统性地扫描所有包 (`cascade-interfaces`, `cascade-runtime`, `cascade-py`, `cascade-cli`) 和 `tests` 目录中的 Python 文件。
2.  将所有错误的、跨包的相对导入语句，替换为正确的、绝对的导入语句。
3.  确保修复后的代码库能够通过 `pytest` 的测试加载阶段。

### 基本原理
我们将采用 `patch_file` 操作，逐个文件、精确地修正导入语句。基本原则是将所有指向 `spec`, `runtime`, `graph.model`, `interfaces.protocols` 等核心组件的导入路径，都统一为以 `cascade.` 开头的绝对路径。这利用了 `uv pip install -e .` 在工作区模式下正确设置 `PYTHONPATH` 的能力，使得所有包都能看到一个统一的 `cascade` 命名空间。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #comp/interfaces #comp/runtime #comp/py #comp/cli #scope/dx #ai/instruct #task/domain/build #task/object/imports #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修复 `cascade-interfaces` 包内部的循环依赖

`spec/task.py` 错误地引用了 `runtime` 包，这造成了层级和依赖的混乱。我们将其修正为引用 `interfaces` 包内的正确协议。

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/spec/task.py
~~~~~
~~~~~python
if TYPE_CHECKING:
    from cascade.runtime.protocols import CachePolicy
~~~~~
~~~~~python
if TYPE_CHECKING:
    from cascade.interfaces.protocols import CachePolicy
~~~~~

#### Acts 2: 修复 `cascade-runtime` 包的导入

这个包依赖于 `cascade-interfaces`，我们需要将所有 `..spec` 或 `..graph.model` 这样的相对引用改为绝对引用。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
~~~~~
~~~~~python
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.interfaces.spec.routing import Router
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.task import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
~~~~~
~~~~~python
        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/serialize.py
~~~~~
~~~~~python
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from ..spec.routing import Router
from ..spec.task import Task
~~~~~
~~~~~python
from cascade.interfaces.spec.common import Param
from cascade.interfaces.spec.constraint import ResourceConstraint
from cascade.interfaces.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.interfaces.spec.routing import Router
from cascade.interfaces.spec.task import Task
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition, Inject
~~~~~
~~~~~python
from cascade.interfaces.spec.resource import ResourceDefinition, Inject
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
~~~~~
~~~~~python
from cascade.interfaces.spec.common import Param
from cascade.interfaces.spec.lazy_types import LazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.interfaces.spec.resource import Inject
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
from ..spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
~~~~~
~~~~~python
from cascade.interfaces.spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

#### Acts 3: 修复 `cascade-py` 包的导入 (核心问题)

这是导致整个 `cascade` 命名空间损坏的根源。所有相对导入都需要改为绝对导入。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
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
from .runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from .runtime.exceptions import DependencyMissingError
from .runtime.protocols import Connector
from .adapters.solvers.native import NativeSolver
from .adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
~~~~~
~~~~~python
# Core Specs
from cascade.interfaces.spec.task import task
from cascade.interfaces.spec.lazy_types import LazyResult
from cascade.interfaces.spec.routing import Router
from cascade.interfaces.spec.resource import resource, inject
from cascade.interfaces.spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from cascade.interfaces.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var

# Legacy / Spec Compat
# We keep Param class import removed/hidden as we are overriding it below.
# from cascade.interfaces.spec.common import Param  <-- Removed

# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector
from cascade.runtime.adapters.solvers.native import NativeSolver
from cascade.runtime.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from cascade.runtime.graph.serialize import to_json, from_json
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/context.py
~~~~~
~~~~~python
from .spec.input import InputSpec
~~~~~
~~~~~python
from cascade.interfaces.spec.input import InputSpec
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/io.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/http.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/shell.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/config.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/sql.py
~~~~~
~~~~~python
from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task, LazyResult
from cascade.interfaces.spec.resource import inject
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/template.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/s3.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/stdio.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/events.py
~~~~~
~~~~~python
from ..runtime.events import Event
~~~~~
~~~~~python
from cascade.runtime.events import Event
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/preview.py
~~~~~
~~~~~python
from ..spec.lazy_types import LazyResult  # NEW
from ..graph.build import build_graph
from ..runtime.engine import Engine
from ..runtime.bus import MessageBus
from ..adapters.solvers.native import NativeSolver
from ..adapters.executors.local import LocalExecutor
~~~~~
~~~~~python
from cascade.interfaces.spec.lazy_types import LazyResult  # NEW
from cascade.runtime.graph.build import build_graph
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.adapters.solvers.native import NativeSolver
from cascade.runtime.adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/visualize.py
~~~~~
~~~~~python
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..graph.model import Node, EdgeType
~~~~~
~~~~~python
from cascade.interfaces.spec.task import LazyResult
from cascade.runtime.graph.build import build_graph
from cascade.interfaces.graph.model import Node, EdgeType
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/testing.py
~~~~~
~~~~~python
from cascade.runtime import Engine
~~~~~
~~~~~python
from cascade.runtime.engine import Engine
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/internal/inputs.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

#### Acts 4: 修复 `cascade-cli` 包的导入

CLI 包依赖 `cascade-py`，也需要修正其导入路径。

~~~~~act
patch_file
packages/cascade-cli/src/cascade/cli/main.py
~~~~~
~~~~~python
from ..spec.task import LazyResult
from ..context import get_current_context
from ..spec.input import ParamSpec


def cli(target: LazyResult[Any]) -> Callable[[], None]:
~~~~~
~~~~~python
from cascade.interfaces.spec.lazy_types import LazyResult
from cascade.context import get_current_context
from cascade.interfaces.spec.input import ParamSpec


def cli(target: "LazyResult[Any]") -> Callable[[], None]:
~~~~~

~~~~~act
patch_file
packages/cascade-cli/src/cascade/cli/main.py
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from cascade import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
~~~~~

#### Acts 5: 修复 `tests` 目录中的导入

最后，修正测试文件中的导入路径，确保它们也能找到正确的模块。

~~~~~act
patch_file
tests/conftest.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
~~~~~

> **注意**: `tests/conftest.py` 的导入本身是正确的绝对路径。它之所以失败，是因为 `cascade` 包的 `__init__.py` 在加载过程中就已损坏。上述修复将解决这个问题，因此 `conftest.py` 无需修改，但我列出此 act 以确认其已被审查。我将移除此 act，因为它不产生任何变更。

~~~~~act
patch_file
tests/interfaces/spec/test_async.py
~~~~~
~~~~~python
from cascade.spec.task import task
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_common.py
~~~~~
~~~~~python
from cascade.spec.common import Param
~~~~~
~~~~~python
from cascade.interfaces.spec.common import Param
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_constraint.py
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.spec.constraint import ResourceConstraint
~~~~~
~~~~~python
from cascade.runtime.graph.build import build_graph
from cascade.interfaces.spec.constraint import ResourceConstraint
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_input_context.py
~~~~~
~~~~~python
from cascade.spec.input import ParamSpec, EnvSpec
~~~~~
~~~~~python
from cascade.interfaces.spec.input import ParamSpec, EnvSpec
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_input_context.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult
~~~~~
~~~~~python
from cascade.interfaces.spec.lazy_types import LazyResult
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_resource.py
~~~~~
~~~~~python
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~python
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event
from cascade.runtime.adapters.executors.local import LocalExecutor
from cascade.runtime.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
tests/interfaces/spec/test_task.py
~~~~~
~~~~~python
from cascade.spec.task import task, LazyResult
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task, LazyResult
~~~~~

### 下一步建议
在应用这些补丁之后，导入问题应该已经解决。请重新运行安装和测试命令来验证修复效果：

1.  **重新安装**:
    ```bash
    uv pip install -e ".[dev]"
    ```
2.  **运行测试**:
    ```bash
    pytest
    ```

如果还有残留的 `ModuleNotFoundError`，很可能是有我遗漏的、需要修正的导入语句，但核心的结构性问题应该已经解决了。
