from enum import Enum
from typing import Any

# Import PortRole from the existing physical layer to maintain compatibility
# and avoid semantic drift between the "Law" (physics) and the "Matter" (physical).
from cascade.spec.physical.ports import PortRole


class PortType(str, Enum):
    """
    Defines the semantic type of data flowing through a port.
    """
    Token = "Token"      # Generic data token
    Ledger = "Ledger"    # Resource ledger
    Any = "Any"          # Any type


class PortDirection(str, Enum):
    """
    Defines the direction of flow for a port relative to the Node.
    """
    INPUT = "input"
    OUTPUT = "output"


class PortDef:
    """
    Descriptor for defining a port on a PhysicsSpec.
    Acts as the definition of a single interface point on a physical node.
    """
    def __init__(
        self,
        name: str,
        direction: PortDirection,
        role: PortRole = PortRole.DATA,
        type_hint: Any = PortType.Any
    ):
        self.name = name
        self.direction = direction
        self.role = role
        self.type_hint = type_hint

    def __set_name__(self, owner, name):
        # We allow the attribute name to act as a fallback or strict mapping validation later.
        pass

    def __repr__(self):
        return f"PortDef(name='{self.name}', dir={self.direction}, role={self.role})"


class Port:
    """
    Namespace factory for defining ports in a declarative style.
    Example:
        data_in = Port.Input("data_in")
    """
    
    @staticmethod
    def Input(name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        return PortDef(name, PortDirection.INPUT, role, type)

    @staticmethod
    def Output(name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        return PortDef(name, PortDirection.OUTPUT, role, type)