from typing import TypeVar, Generic, Callable, Optional, Union, List
import inspect

from cascade.runtime.protocols import CachePolicy
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import (
    LazyResult,
    MappedLazyResult,
    RetryPolicy,
)  # NEW import location

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


def _with_constraints(self: LazyResult, **kwargs) -> LazyResult:
    self._constraints = ResourceConstraint(requirements=kwargs)
    return self


LazyResult.with_constraints = _with_constraints


def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


MappedLazyResult.run_if = _mapped_run_if
