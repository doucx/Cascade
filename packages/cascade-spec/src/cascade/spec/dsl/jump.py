from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .fluent import LazyResult


@dataclass
class Jump:
    target_key: str
    data: Any = None


@dataclass
class JumpSelector:
    routes: dict[str, LazyResult | None]
    _uuid: str = field(default_factory=lambda: str(uuid4()))

    def __hash__(self):
        return hash(self._uuid)
