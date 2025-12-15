from typing import TypeVar, Generic, Callable, Any, Dict, Optional
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

T = TypeVar("T")


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

    def __hash__(self):
        return hash(self._uuid)


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
