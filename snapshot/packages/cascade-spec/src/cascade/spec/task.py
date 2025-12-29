from typing import (
    TypeVar,
    Generic,
    Callable,
    Optional,
    Union,
    List,
    TYPE_CHECKING,
    overload,
)
import inspect

if TYPE_CHECKING:
    pass

from cascade.spec.lazy_types import (
    LazyResult,
    MappedLazyResult,
)

T = TypeVar("T")


# --- Task Definition ---


class Task(Generic[T]):
    def __init__(
        self,
        func: Callable[..., T],
        name: Optional[str] = None,
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
        self._potential_tco_targets: Optional[List["Task"]] = None

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def map(self, **kwargs) -> MappedLazyResult[List[T]]:
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
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Callable[[Callable[..., T]], Task[T]]: ...


@overload
def task(
    func: Callable[..., T],
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Task[T]: ...


def task(
    func: Optional[Callable[..., T]] = None,
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name, pure=pure, mode=mode)

    if func:
        return wrapper(func)
    else:
        return wrapper
