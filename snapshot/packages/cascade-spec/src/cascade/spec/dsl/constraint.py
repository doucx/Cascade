from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceConstraint:
    requirements: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.requirements

    def __bool__(self):
        return not self.is_empty()


def with_constraints(**kwargs) -> ResourceConstraint:
    return ResourceConstraint(requirements=kwargs)


@dataclass
class GlobalConstraint:
    id: str
    scope: str  # e.g., "global", "project:quipu", "task:openai_request"
    type: str  # "concurrency", "rate_limit", "pause"
    params: dict[str, Any]  # e.g., {"limit": 5, "window": 60}
    expires_at: float | None = None
