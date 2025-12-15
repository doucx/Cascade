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
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class Param:
    """Represents a runtime parameter."""

    name: str
    default: Any = None
    type: Any = None
    description: str = ""


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

    def __hash__(self):
        return hash(self._uuid)

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


def task(func: Callable[..., T]) -> Task[T]:
    """Decorator to convert a function into a Task."""
    return Task(func)
