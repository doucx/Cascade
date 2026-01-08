from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from cascade.spec.runtime.interfaces import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class LazyResult(Generic[T]):
    task: Any  # Should be 'Task[T]'
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
        return hash(self._uuid)

    def run_if(self, condition: "LazyResult") -> "LazyResult[T]":
        self._condition = condition
        return self

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "LazyResult[T]":
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: "CachePolicy") -> "LazyResult[T]":
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        # Import internally to avoid circular dependency at module level
        from cascade.spec.dsl.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self

    def after(self, *predecessors: "LazyResult") -> "LazyResult[T]":
        self._dependencies.extend(predecessors)
        return self


@dataclass
class MappedLazyResult(Generic[T]):
    factory: Any  # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List[LazyResult] = field(default_factory=list)
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
        return hash(self._uuid)

    def run_if(self, condition: LazyResult) -> "MappedLazyResult[T]":
        self._condition = condition
        return self

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "MappedLazyResult[T]":
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: "CachePolicy") -> "MappedLazyResult[T]":
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "MappedLazyResult[T]":
        from cascade.spec.dsl.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self

    def after(self, *predecessors: LazyResult) -> "MappedLazyResult[T]":
        self._dependencies.extend(predecessors)
        return self
