from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class Ref:
    uri: str

    meta: Dict[str, Any] = field(default_factory=dict)
