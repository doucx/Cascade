from dataclasses import dataclass
from enum import Enum


class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"  # Legacy: Used for Stainer release
    RESOURCE_REQUEST = "RESOURCE_REQUEST"  # New: Used for Bleacher input (amount)
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"


@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"
