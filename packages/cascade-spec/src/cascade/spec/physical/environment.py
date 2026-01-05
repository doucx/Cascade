from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ResourceDef:
    name: str
    capacity: int = 1
    type: str = "discrete"


@dataclass(frozen=True)
class EnvironmentDef:
    resources: List[ResourceDef] = field(default_factory=list)
