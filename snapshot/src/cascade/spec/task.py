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
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


from .common import Param

@dataclass
class LazyResult(Generic[T]):
    """
    A placeholder for the result of a task execution.
    It holds the task that produces it and the arguments passed to that task.
    """

    task: "Task[T]"
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[CachePolicy] = None
    _condition: Optional["LazyResult"] = None

    def __hash__(self):
        return hash(self._uuid)

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


def task(
    func: Optional[Callable[..., T]] = None, *, name: Optional[str] = None
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    Can be used as a simple decorator (`@task`) or as a factory with
    arguments (`@task(name='custom_name')`).
    """
    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name)

    if func:
        # Used as @task
        return wrapper(func)
    else:
        # Used as @task(name="...")
        return wrapper
