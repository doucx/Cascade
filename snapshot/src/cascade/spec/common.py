from typing import Any
from dataclasses import dataclass


@dataclass
class Param:
    """Represents a runtime parameter."""

    name: str
    default: Any = None
    type: Any = None
    description: str = ""