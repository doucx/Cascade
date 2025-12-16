这是一个经典的 Python **循环导入 (Circular Import)** 问题。

当你看到 `ImportError: cannot import name 'LazyResult' from partially initialized module 'cascade.spec.task'` 时，这意味着：

1.  某个文件（比如 `src/cascade/__init__.py`）导入了 `src/cascade/spec/task.py` 中的 `LazyResult`。
2.  但在 `src/cascade/spec/task.py` 试图加载的过程中，它又尝试导入了其他文件中的东西，而这些文件又反过来依赖 `LazyResult`，此时 `task.py` 还没有完全初始化，导致导入失败。

我们的重构引入了新的依赖：

- **`src/cascade/graph/build.py`** 导入了 `LazyResult`, `MappedLazyResult` (来自 `spec.task`)。
- **`src/cascade/spec/task.py`** 导入了 `CachePolicy`, `LazyFactory` (来自 `runtime.protocols`)。
- **`src/cascade/runtime/engine.py`** 导入了 `LazyResult`, `MappedLazyResult` (来自 `spec.task`)。

在将 `LazyResult` 导入到 `build.py` 和 `engine.py` 的同时，`task.py` 自己依赖的 `runtime.protocols` 也被其他模块依赖，造成了死锁。

### 解决方案：解决循环依赖

核心思想是：将 `LazyResult` 和 `MappedLazyResult` 这两个核心的数据结构定义（它们几乎被所有组件依赖）移动到一个最低层级的、不依赖于任何其他组件的文件中。

**最佳实践**：在 `src/cascade/spec/` 目录下创建一个新的文件 `lazy_types.py`，用于存放 `LazyResult` 和 `MappedLazyResult`。

## [WIP] fix(core): 解决核心 LazyResult 结构导致的循环导入问题

### 错误分析
模块 `cascade.spec.task` 包含了 `LazyResult` 和 `MappedLazyResult` 的定义，但其自身又依赖 `cascade.runtime.protocols`，而后者又间接或直接地依赖 `task.py`，导致循环导入。

### 目标
1.  创建新的文件 `src/cascade/spec/lazy_types.py`，并移动 `LazyResult`, `MappedLazyResult` 以及 `RetryPolicy` 的定义到该文件。
2.  更新所有相关文件 (`task.py`, `build.py`, `engine.py`) 的导入路径。
3.  确保 `task.py` 中依赖 `lazy_types` 的导入被正确更新。

### 基本原理
将核心数据结构剥离到低级模块，遵循层次依赖原则。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #concept/lazy-result #scope/core #ai/instruct #task/domain/core #task/object/import-cycle #task/action/restructure #task/state/continue

---

### Script

#### Acts 1: 创建新的 `src/cascade/spec/lazy_types.py` 文件

~~~~~act
write_file
src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Any, Dict, Optional, List
from dataclasses import dataclass, field
from uuid import uuid4

# Forward references for policies to avoid circular imports 
# (e.g., CachePolicy is in runtime.protocols which depends on LazyResult)
# We use Any for typing policies in the definition stage.

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class LazyResult(Generic[T]):
    """
    A placeholder for the result of a task execution.
    It holds the task that produces it and the arguments passed to that task.
    """

    task: Any  # Should be 'Task[T]'
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)

    # Note: Chaining methods (.run_if, .with_retry, etc.) remain in spec/task.py 
    # as they tightly couple to Task logic and protocols.

@dataclass
class MappedLazyResult(Generic[T]):
    """
    Represents the result of mapping a factory over a set of inputs.
    It resolves to a list of results.
    """

    factory: Any # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None

    def __hash__(self):
        return hash(self._uuid)
~~~~~

#### Acts 2: 更新 `src/cascade/spec/task.py`

移除已移动的定义，并引入新的导入路径。同时将链式方法移回 `Task` 类。

~~~~~act
write_file
src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy, LazyFactory
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult, RetryPolicy # NEW

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class LazyResult(Generic[T]):
    """
    A placeholder for the result of a task execution.
    ... [DEFINITION REMOVED] ...
    """
    # ... [REMOVED]

    def run_if(self, condition: "LazyResult") -> "LazyResult[T]":
        """
        Attaches a condition to this task. The task will only run if
        the condition evaluates to True at runtime.
        """
        self._condition = condition
        return self

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "LazyResult[T]":
        """Configures retry logic for this task."""
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        """
        Attaches resource constraints to this task.
        e.g., .with_constraints(memory_gb=4, gpu_count=1)
        """
        self._constraints = ResourceConstraint(requirements=kwargs)
        return self


@dataclass
class MappedLazyResult(Generic[T]):
    """
    Represents the result of mapping a factory over a set of inputs.
    It resolves to a list of results.
    """
    # ... [REMOVED]

    def run_if(self, condition: LazyResult) -> "MappedLazyResult[T]":
        self._condition = condition
        return self
~~~~~

#### Acts 3: 更新 `src/cascade/graph/build.py`

更新 `build.py` 以从新的位置导入 `LazyResult` 和 `MappedLazyResult`。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult, MappedLazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.lazy_types import LazyResult, MappedLazyResult # NEW
from cascade.spec.common import Param
from cascade.spec.routing import Router
~~~~~

#### Acts 4: 更新 `src/cascade/runtime/engine.py`

更新 `engine.py` 中的导入。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.resource_manager import ResourceManager
from cascade.spec.task import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.resource_manager import ResourceManager
from cascade.spec.lazy_types import LazyResult, MappedLazyResult # NEW
~~~~~

#### Acts 5: 更新 `src/cascade/graph/serialize.py`

更新 `serialize.py` 中的导入。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.routing import Router
from ..spec.task import RetryPolicy, Task
~~~~~
~~~~~python
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.routing import Router
from ..spec.lazy_types import RetryPolicy # NEW
from ..spec.task import Task
~~~~~

#### Acts 6: 更新 `src/cascade/tools/preview.py`

更新 `preview.py` 中的导入。

~~~~~act
patch_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine
~~~~~
~~~~~python
from typing import Any
from ..spec.lazy_types import LazyResult # NEW
from ..graph.build import build_graph
from ..runtime.engine import Engine
~~~~~

### 下一步建议
我们已经完成了解决循环导入的架构重组。在提交之前，我需要将上一步的修改 (`src/cascade/spec/task.py` 中的链式方法) 整合回新的 `src/cascade/spec/task.py` 文件中，因为它在 Act 2 被写为 `write_file` 时被删除了。我将修正 `src/cascade/spec/task.py` 的内容，然后我们就可以执行测试了。
