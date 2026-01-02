from enum import Enum
from dataclasses import dataclass


class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"


@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"
