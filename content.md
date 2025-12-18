简要回答：
这是典型的多包重构后的导入路径混乱。虽然文件物理上被移动到了 `packages/cascade-interfaces/src/cascade/spec`，但在 Python 的命名空间中，它们映射为 `cascade.spec`，而不是 `cascade.interfaces.spec`。同样，`cascade.runtime.protocols` 也应更新为 `cascade.interfaces.protocols`。

我将生成一个计划来批量修复核心包（`cascade-py`, `cascade-runtime`, `cascade-cli`）中的这些导入错误。

## [WIP] fix(core): 修正多包重构后的导入路径错误

### 用户需求
修复运行 `pytest` 时出现的 `ModuleNotFoundError: No module named 'cascade.interfaces'` 错误。这主要是由于重构后，代码中的导入路径（如 `cascade.interfaces.spec`）与实际的命名空间布局（应为 `cascade.spec`）不匹配导致的。

### 评论
这种路径错误在 Monorepo 迁移中非常常见。关键是要理解 Hatchling 的 `packages = ["src/cascade"]` 配置实际上是将所有包的内容合并到了同一个顶层 `cascade` 命名空间下，并没有为每个包（如 `cascade-interfaces`）创建单独的二级命名空间。

### 目标
1.  修正 `cascade-py`、`cascade-runtime` 和 `cascade-cli` 中所有错误的 `cascade.interfaces.spec.*` 引用为 `cascade.spec.*`。
2.  修正所有过时的 `cascade.runtime.protocols` 引用为 `cascade.interfaces.protocols`。
3.  修正 `cascade.interfaces.graph` 引用为 `cascade.graph`。

### 基本原理
我们必须遵循 Python 的 Namespace Package 规则。`packages/cascade-interfaces/src/cascade/spec/task.py` 在安装后，其导入路径就是 `cascade.spec.task`。任何中间的目录名（如 `interfaces`）如果不是 `src/cascade` 下的子目录，就不应该出现在导入路径中。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/config #scope/core #ai/instruct #task/domain/core #task/object/monorepo #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修正 `cascade-py` 的导入路径

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
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
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/context.py
~~~~~
~~~~~python
from contextvars import ContextVar
from typing import Dict, List
from cascade.interfaces.spec.input import InputSpec

class WorkflowContext:
~~~~~
~~~~~python
from contextvars import ContextVar
from typing import Dict, List
from cascade.spec.input import InputSpec

class WorkflowContext:
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/tools/visualize.py
~~~~~
~~~~~python
from typing import Any
from cascade.interfaces.spec.task import LazyResult
from cascade.runtime.graph.build import build_graph
from cascade.interfaces.graph.model import Node, EdgeType


def visualize(target: LazyResult[Any]) -> str:
~~~~~
~~~~~python
from typing import Any
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.graph.build import build_graph
from cascade.graph.model import Node, EdgeType


def visualize(target: LazyResult[Any]) -> str:
~~~~~

#### Acts 2: 修正 `cascade-cli` 的导入路径

~~~~~act
patch_file
packages/cascade-cli/src/cascade/cli/main.py
~~~~~
~~~~~python
    typer = None

from cascade.interfaces.spec.lazy_types import LazyResult
from cascade.context import get_current_context
from cascade.interfaces.spec.input import ParamSpec


def cli(target: "LazyResult[Any]") -> Callable[[], None]:
~~~~~
~~~~~python
    typer = None

from cascade.spec.lazy_types import LazyResult
from cascade.context import get_current_context
from cascade.spec.input import ParamSpec


def cli(target: "LazyResult[Any]") -> Callable[[], None]:
~~~~~

#### Acts 3: 修正 `cascade-runtime` 的导入路径 (Graph & Build)

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.interfaces.spec.routing import Router


class GraphBuilder:
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


class GraphBuilder:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
~~~~~
~~~~~python
        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.lazy_types import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/serialize.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from cascade.interfaces.spec.common import Param
from cascade.interfaces.spec.constraint import ResourceConstraint
from cascade.interfaces.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.interfaces.spec.routing import Router
from cascade.interfaces.spec.task import Task
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task
~~~~~

#### Acts 4: 修正 `cascade-runtime` 的导入路径 (Runtime Core)

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/__init__.py
~~~~~
~~~~~python
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from .protocols import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
~~~~~
~~~~~python
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from cascade.interfaces.protocols import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.interfaces.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    ResourceAcquired,
    ResourceReleased,
)
from cascade.runtime.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~
~~~~~python
    ResourceAcquired,
    ResourceReleased,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.interfaces.spec.common import Param
from cascade.interfaces.spec.lazy_types import LazyResult
from cascade.runtime.protocols import StateBackend
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.interfaces.spec.resource import Inject
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.protocols import StateBackend
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    ResourceAcquired,
    ResourceReleased,
)
from cascade.interfaces.spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
from .protocols import Connector
~~~~~
~~~~~python
    ResourceAcquired,
    ResourceReleased,
)
from cascade.spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
from cascade.interfaces.protocols import Connector
~~~~~

#### Acts 5: 修正 `cascade-runtime` 的导入路径 (Adapters)

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
from typing import Dict, List, Set
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan


class NativeSolver:
~~~~~
~~~~~python
from typing import Dict, List, Set
from cascade.graph.model import Graph, Node
from cascade.interfaces.protocols import ExecutionPlan


class NativeSolver:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
from typing import Dict, List, Any, Optional
from collections import defaultdict
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan
from cascade.interfaces.spec.lazy_types import LazyResult, MappedLazyResult

try:
~~~~~
~~~~~python
from typing import Dict, List, Any, Optional
from collections import defaultdict
from cascade.graph.model import Graph, Node
from cascade.interfaces.protocols import ExecutionPlan
from cascade.spec.lazy_types import LazyResult, MappedLazyResult

try:
~~~~~

### 下一步建议
一旦核心代码的导入路径被修复，我建议运行 `pytest` 来识别剩余的错误。根据经验，测试文件（`tests/`）中肯定还存在大量类似的路径引用错误，需要在一个单独的计划中进行批量修复。
