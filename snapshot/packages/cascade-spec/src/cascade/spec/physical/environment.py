from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResourceDef:
    name: str
    capacity: int = 1
    type: str = "discrete"


@dataclass(frozen=True)
class EnvironmentDef:
    resources: list[ResourceDef] = field(default_factory=list)
