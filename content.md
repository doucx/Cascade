好的，我将重新整理 `src/cascade/spec/task.py` 的内容。在 Act 1 中，我们创建了 `lazy_types.py` 来存储核心数据结构。现在，`task.py` 将重新聚焦于 **Task 定义** 和 **LazyResult 的链式方法**（这些方法必须在 `Task` 模块中，因为它们依赖于 `Task` 和 `CachePolicy` 等）。

## [WIP] fix(task): 重新整合 LazyResult 的链式方法到 task.py

### 目标
用完整的、正确的代码替换 `src/cascade/spec/task.py` 的内容。新的代码将从 `lazy_types.py` 导入核心类，并为 `LazyResult` 和 `MappedLazyResult` 添加所有的链式方法。

### 基本原理
确保 `Task` 模块的功能完整性，并遵循新的模块结构。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #concept/lazy-result #scope/core #ai/instruct #task/domain/core #task/object/import-cycle #task/action/restructure #task/state/continue

---

### Script

#### Acts 1: 重新写入 `src/cascade/spec/task.py` 的完整内容

整合了所有逻辑，包括导入和链式方法。

~~~~~act
write_file
src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union, List
from dataclasses import dataclass
import inspect

from cascade.runtime.protocols import CachePolicy, LazyFactory
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult, RetryPolicy # NEW import location

T = TypeVar("T")


# --- Task Definition ---

class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        # When called, it creates a LazyResult, inheriting RetryPolicy etc. from the Task? 
        # No, policies are set on the LazyResult object itself via chaining.
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def map(self, **kwargs) -> MappedLazyResult[List[T]]:
        """
        Applies the task over a sequence of inputs.
        """
        return MappedLazyResult(factory=self, mapping_kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"


# --- Decorator ---

def task(
    func: Optional[Callable[..., T]] = None, *, name: Optional[str] = None
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    """

    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name)

    if func:
        return wrapper(func)
    else:
        return wrapper


# --- Extend LazyResult/MappedLazyResult with Chaining Methods (Mixin-like) ---
# We dynamically attach the chaining methods to the imported LazyResult class.

def _run_if(self: LazyResult, condition: LazyResult) -> LazyResult:
    self._condition = condition
    return self
LazyResult.run_if = _run_if

def _with_retry(self: LazyResult, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0) -> LazyResult:
    self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
    return self
LazyResult.with_retry = _with_retry

def _with_cache(self: LazyResult, policy: CachePolicy) -> LazyResult:
    self._cache_policy = policy
    return self
LazyResult.with_cache = _with_cache

def _with_constraints(self: LazyResult, **kwargs) -> LazyResult:
    self._constraints = ResourceConstraint(requirements=kwargs)
    return self
LazyResult.with_constraints = _with_constraints

def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self
MappedLazyResult.run_if = _mapped_run_if
~~~~~

### 下一步建议
我们现在应该拥有一个结构完整的 `Cascade` 核心库。循环导入问题已解决，`Engine` 和 `Executor` 也已重构，且所有相关的单元和集成测试（包括 `test_local.py` 和 `test_control_flow.py`）都已更新。

是时候运行完整的测试套件并生成最终的 `[COMMIT]` 计划了。请指示执行测试。
