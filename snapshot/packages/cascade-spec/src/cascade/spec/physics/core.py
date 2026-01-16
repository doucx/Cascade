from enum import Enum
from typing import Any

# Import PortRole from the existing physical layer to maintain compatibility
# and avoid semantic drift between the "Law" (physics) and the "Matter" (physical).
from ..physical.ports import PortRole


class PortType(str, Enum):
    Token = "Token"  # Generic data token
    Ledger = "Ledger"  # Resource ledger
    Any = "Any"  # Any type


class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class PortDef:
    def __init__(
        self,
        name: str,
        direction: PortDirection,
        role: PortRole = PortRole.DATA,
        type_hint: Any = PortType.Any,
        is_map: bool = False,
        prefix: str = "",
    ):
        self.name = name
        self.direction = direction
        self.role = role
        self.type_hint = type_hint
        self.is_map = is_map
        self.prefix = prefix

    def __set_name__(self, owner, name):
        # We allow the attribute name to act as a fallback or strict mapping validation later.
        pass

    def __repr__(self):
        return f"PortDef(name='{self.name}', dir={self.direction}, role={self.role}, map={self.is_map})"


class Port:
    @staticmethod
    def Input(
        name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any
    ) -> PortDef:
        return PortDef(name, PortDirection.INPUT, role, type)

    @staticmethod
    def Output(
        name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any
    ) -> PortDef:
        return PortDef(name, PortDirection.OUTPUT, role, type)

    @staticmethod
    def MapInput(role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        return PortDef("*", PortDirection.INPUT, role, type, is_map=True)

    @staticmethod
    def MapOutput(
        prefix: str = "", role: PortRole = PortRole.DATA, type: Any = PortType.Any
    ) -> PortDef:
        return PortDef(
            "*", PortDirection.OUTPUT, role, type, is_map=True, prefix=prefix
        )
