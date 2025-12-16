# [WIP] fix(runtime): 解决 Resolvers 与 Internal Inputs 之间的循环依赖

## 摘要头
## [WIP] fix(runtime): 解决 Resolvers 与 Internal Inputs 之间的循环依赖

### 用户需求
修复导致 `ImportError` 的循环依赖问题。该问题是由 `runtime.resolvers` 导入 `internal.inputs`，而 `internal.inputs` 又依赖 `spec.task`，最终 `spec.task` 又间接依赖 `runtime` 包初始化引起的。

### 评论
这是一个经典的 Python 循环导入问题。`ArgumentResolver` 需要识别特殊的内部任务 `_get_param_value`，但直接在模块顶层导入它会导致闭环。解决方案是将导入移至方法内部（运行时导入），从而打破导入时的依赖链。

### 目标
1.  修改 `src/cascade/runtime/resolvers.py`，将 `_get_param_value` 的导入移至 `resolve` 方法内部。
2.  (可选) 优化 `src/cascade/spec/task.py` 中的类型提示导入，进一步减少耦合风险。

### 基本原理
通过延迟导入（Lazy Import），我们可以确保在模块初始化阶段不会触发循环依赖。`_get_param_value` 仅在 `resolve` 方法执行时才需要，因此在方法内导入是安全的。

### 标签
#intent/fix #flow/draft #priority/critical #comp/runtime #scope/core #ai/refine #task/domain/core #task/object/dependency-cycle #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 将 ArgumentResolver 中的导入移至局部

移除顶层导入，改为在 `resolve` 方法内部导入 `_get_param_value`。

~~~~~act
patch_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.internal.inputs import _get_param_value


class ArgumentResolver:
~~~~~
~~~~~new
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError


class ArgumentResolver:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        if node.callable_obj is _get_param_value:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # 1. Prepare arguments from literals and upstream results
~~~~~
~~~~~new
        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        # Local import to avoid circular dependency with internal.inputs -> spec.task -> runtime
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # 1. Prepare arguments from literals and upstream results
~~~~~

#### Acts 2: 优化 spec/task.py 的导入 (最佳实践)

为了防止未来发生类似的循环引用，将 `CachePolicy` 的导入移至 `TYPE_CHECKING` 块中。这解耦了 `spec` 层在运行时对 `runtime` 层的依赖。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~old
from typing import TypeVar, Generic, Callable, Optional, Union, List
import inspect

from cascade.runtime.protocols import CachePolicy
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import (
    LazyResult,
~~~~~
~~~~~new
from typing import TypeVar, Generic, Callable, Optional, Union, List, TYPE_CHECKING
import inspect

if TYPE_CHECKING:
    from cascade.runtime.protocols import CachePolicy

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import (
    LazyResult,
~~~~~

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~old
def _with_retry(
    self: LazyResult, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
) -> LazyResult:
    self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
    return self


LazyResult.with_retry = _with_retry


def _with_cache(self: LazyResult, policy: CachePolicy) -> LazyResult:
    self._cache_policy = policy
    return self


LazyResult.with_cache = _with_cache
~~~~~
~~~~~new
def _with_retry(
    self: LazyResult, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
) -> LazyResult:
    self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
    return self


LazyResult.with_retry = _with_retry


def _with_cache(self: LazyResult, policy: "CachePolicy") -> LazyResult:
    self._cache_policy = policy
    return self


LazyResult.with_cache = _with_cache
~~~~~

### 下一步建议
这次修复应该能解决 `ImportError`。之后，请运行 `pytest` 验证之前的 7 个功能性失败是否也因 Acts 1-7 (在前一个 Plan 中) 而得到解决。如果还有失败，我们将针对具体错误进行修复。
