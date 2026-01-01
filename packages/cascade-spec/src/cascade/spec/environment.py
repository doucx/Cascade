from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ResourceDef:
    name: str
    capacity: int = 1
    """The total available units of this resource in the environment."""


@dataclass(frozen=True)
class EnvironmentDef:
    resources: List[ResourceDef] = field(default_factory=list)
    """The set of all resources objectively available in this physical field."""