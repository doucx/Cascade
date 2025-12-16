好的，我们按照规划，分步实施。

这是第一步：**定义核心协议与数据结构**。

我们将首先在协议层正式定义“可映射工厂”的契约，然后在 `Task` 类中实现这一契约，引入 `MappedLazyResult` 结构。这不会影响现有代码的运行，但为后续的运行时支持做好了数据准备。

## [WIP] feat(core): Define `LazyFactory` protocol and `MappedLazyResult`

### 用户需求
开始实现重新设计的 `.map()` 功能。第一步需要建立基础架构：定义 `LazyFactory` 协议接口，并在 `Task` 类中实现 `.map()` 方法，使其返回一个新的 `MappedLazyResult` 对象。

### 评论
这是架构升级的基础。通过显式定义 `LazyFactory` 协议，我们为未来所有的“值工厂”（如 `cs.shell`, `cs.sql`）确立了统一的行为标准。引入 `MappedLazyResult` 则为图构建器提供了一个明确的信号，表明这里存在一个需要动态展开的结构，而不是一个静态的任务调用。

### 目标
1.  在 `protocols.py` 中定义 `LazyFactory` 协议。
2.  在 `task.py` 中定义 `MappedLazyResult` 数据类。
3.  在 `Task` 类中实现 `.map()` 方法。

### 基本原理
将接口定义与运行时逻辑实现分离，有助于保持代码变更的清晰和原子性。本步骤仅关注“定义”，确保数据结构正确，无需担心执行逻辑的复杂性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/interfaces #concept/map #scope/api #ai/instruct #task/domain/core #task/object/map-api #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义 `LazyFactory` 协议

我们在运行时协议中增加 `LazyFactory` 定义。它要求实现者提供一个 `.map` 方法。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...
~~~~~
~~~~~python
    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...


class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """

    def map(self, **kwargs) -> Any:
        """
        Creates a mapped lazy result by applying this factory over iterables.
        """
        ...
~~~~~

#### Acts 2: 实现 `MappedLazyResult` 和 `Task.map`

我们在 `task.py` 中引入 `MappedLazyResult` 类，并修改 `Task` 类以实现 `LazyFactory` 协议。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy

T = TypeVar("T")


@dataclass
class RetryPolicy:
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy, LazyFactory

T = TypeVar("T")


@dataclass
class RetryPolicy:
~~~~~

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self


class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        # Signature inspection for validation (future enhancement)
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"
~~~~~
~~~~~python
    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self


@dataclass
class MappedLazyResult(Generic[T]):
    """
    Represents the result of mapping a factory over a set of inputs.
    It resolves to a list of results.
    """

    factory: LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None

    def __hash__(self):
        return hash(self._uuid)

    def run_if(self, condition: LazyResult) -> "MappedLazyResult[T]":
        self._condition = condition
        return self


class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        # Signature inspection for validation (future enhancement)
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def map(self, **kwargs) -> MappedLazyResult[List[T]]:
        """
        Applies the task over a sequence of inputs.
        
        Args:
            **kwargs: Arguments where values are iterables (or LazyResults resolving to iterables).
                      All iterables must have the same length.
        
        Returns:
            A MappedLazyResult that resolves to a list of outputs.
        """
        return MappedLazyResult(factory=self, mapping_kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"
~~~~~

### 下一步建议
我们已经完成了数据结构的定义。现在 `Task.map()` 会返回一个 `MappedLazyResult` 对象，但系统还不知道如何处理它。接下来的关键步骤是**升级运行时**：首先修改 `GraphBuilder` 以识别并构建映射节点，然后彻底改造 `Engine` 以支持动态展开和执行这些节点。
