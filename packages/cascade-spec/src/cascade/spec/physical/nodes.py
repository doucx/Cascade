from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ports import PortDef


@dataclass
class Token:
    payload: Any

    trace: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhysicsNode:
    id: str

    name: str


@dataclass
class PhysicsDataNode(PhysicsNode):
    capacity: int = 1

    initial_tokens: int = 0

    initial_payload: Any = None


@dataclass
class PhysicsFuncNode(PhysicsNode):
    input_ports: dict[str, PortDef] = field(default_factory=dict)

    output_ports: dict[str, PortDef] = field(default_factory=dict)
