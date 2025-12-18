from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class ResourceConstraint:
    """
    Defines the resource requirements for a Task.

    The keys represent the resource name (e.g., "memory_gb", "gpu_count")
    and the values represent the required amount (literal value or a LazyResult).
    """

    requirements: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.requirements

    def __bool__(self):
        return not self.is_empty()


def with_constraints(**kwargs) -> ResourceConstraint:
    """Helper function for task definitions."""
    return ResourceConstraint(requirements=kwargs)
