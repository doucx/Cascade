from typing import TypeVar, Generic, Callable, Optional, Union, List, TYPE_CHECKING
import inspect

# This import creates a cycle: graph -> spec.task -> spec.protocols -> graph.model
# It must be guarded by TYPE_CHECKING.
if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy

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
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: Optional[List["Task"]] = None

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


def _with_cache(self: LazyResult, policy: "CachePolicy") -> LazyResult:
    self._cache_policy = policy
    return self


LazyResult.with_cache = _with_cache


def _with_constraints(self: LazyResult, **kwargs) -> LazyResult:
    self._constraints = ResourceConstraint(requirements=kwargs)
    return self


LazyResult.with_constraints = _with_constraints


def _after(self: LazyResult, *predecessors: LazyResult) -> LazyResult:
    """
    Explicitly schedules this task to run after the given predecessor tasks,
    without taking their output as input.
    """
    self._dependencies.extend(predecessors)
    return self


LazyResult.after = _after


# --- MappedLazyResult Mixins ---


def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


def _mapped_after(
    self: MappedLazyResult, *predecessors: LazyResult
) -> MappedLazyResult:
    self._dependencies.extend(predecessors)
    return self


MappedLazyResult.run_if = _mapped_run_if
MappedLazyResult.after = _mapped_after
MappedLazyResult.with_retry = _with_retry
MappedLazyResult.with_cache = _with_cache
MappedLazyResult.with_constraints = _with_constraints
