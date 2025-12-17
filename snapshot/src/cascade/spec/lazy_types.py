from typing import TypeVar, Generic, Any, Dict, Optional
from dataclasses import dataclass, field
from uuid import uuid4

# Forward references for policies to avoid circular imports
# (e.g., CachePolicy is in runtime.protocols which depends on LazyResult)
# We use Any for typing policies in the definition stage.

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class LazyResult(Generic[T]):
    """
    A placeholder for the result of a task execution.
    It holds the task that produces it and the arguments passed to that task.
    """

    task: Any  # Should be 'Task[T]'
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)

    # Note: Chaining methods (.run_if, .with_retry, etc.) remain in spec/task.py
    # as they tightly couple to Task logic and protocols.


@dataclass
class MappedLazyResult(Generic[T]):
    """
    Represents the result of mapping a factory over a set of inputs.
    It resolves to a list of results.
    """

    factory: Any  # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)
