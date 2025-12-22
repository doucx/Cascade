from typing import TypeVar, Generic, Callable, Any, Optional
from dataclasses import dataclass
import inspect

T = TypeVar("T")


@dataclass
class ResourceDefinition(Generic[T]):
    """Represents the definition of a resource provider."""

    func: Callable[..., T]
    name: str
    scope: str = "run"  # Default scope

    def __post_init__(self):
        if not inspect.isgeneratorfunction(self.func):
            raise TypeError(
                f"Resource function '{self.name}' must be a generator (use yield)."
            )


class Inject:
    """A marker object to indicate a resource dependency."""

    def __init__(self, resource_name: str):
        self.resource_name = resource_name

    def __repr__(self):
        return f"Inject(resource_name='{self.resource_name}')"


def resource(
    func: Callable[..., T] = None, *, name: Optional[str] = None, scope: str = "run"
):
    """Decorator to define a resource provider."""

    def wrapper(f: Callable[..., T]) -> ResourceDefinition[T]:
        resource_name = name or f.__name__
        return ResourceDefinition(func=f, name=resource_name, scope=scope)

    # Allows using @resource or @resource(name="...")
    if func:
        return wrapper(func)
    return wrapper


def inject(resource_name: str) -> Any:
    """
    Function to be used as a default value in a task's signature
    to declare a dependency on a resource.
    """
    return Inject(resource_name)
