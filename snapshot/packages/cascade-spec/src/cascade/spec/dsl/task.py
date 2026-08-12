from __future__ import annotations

import inspect
from typing import (
    Callable,
    Generic,
    TypeVar,
    overload,
)

from .fluent import (
    LazyResult,
    MappedLazyResult,
)

T = TypeVar("T")


# --- Task Definition ---


class Task(Generic[T]):
    def __init__(
        self,
        func: Callable[..., T],
        name: str | None = None,
        pure: bool = False,
        mode: str = "blocking",
    ):
        self.func = func
        self.name = name or func.__name__
        self.pure = pure
        self.mode = mode
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: list[Task] | None = None

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def map(self, **kwargs) -> MappedLazyResult[list[T]]:
        return MappedLazyResult(factory=self, mapping_kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"


# --- Decorator ---


@overload
def task(
    func: Callable[..., T],
) -> Task[T]: ...


@overload
def task(
    *,
    name: str | None = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Callable[[Callable[..., T]], Task[T]]: ...


@overload
def task(
    func: Callable[..., T],
    *,
    name: str | None = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Task[T]: ...


def task(
    func: Callable[..., T] | None = None,
    *,
    name: str | None = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Task[T] | Callable[[Callable[..., T]], Task[T]]:
    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name, pure=pure, mode=mode)

    if func:
        return wrapper(func)
    else:
        return wrapper
