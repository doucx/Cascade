from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
from .lazy_types import LazyResult


@dataclass
class Jump:
    target_key: str
    data: Any = None


@dataclass
class JumpSelector:
    routes: Dict[str, Optional[LazyResult]]
    _uuid: str = field(default_factory=lambda: str(uuid4()))

    def __hash__(self):
        return hash(self._uuid)
