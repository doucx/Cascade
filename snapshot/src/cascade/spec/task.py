from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy, LazyFactory
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult, RetryPolicy # NEW

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
    ... [DEFINITION REMOVED] ...
    """
    # ... [REMOVED]

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

    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        """
        Attaches resource constraints to this task.
        e.g., .with_constraints(memory_gb=4, gpu_count=1)
        """
        self._constraints = ResourceConstraint(requirements=kwargs)
        return self


@dataclass
class MappedLazyResult(Generic[T]):
    """
    Represents the result of mapping a factory over a set of inputs.
    It resolves to a list of results.
    """
    # ... [REMOVED]

    def run_if(self, condition: LazyResult) -> "MappedLazyResult[T]":
        self._condition = condition
        return self