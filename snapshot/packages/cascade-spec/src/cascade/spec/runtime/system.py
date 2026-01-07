from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ControlCommand(StrEnum):
    HALT = "HALT"  # Immediate shutdown
    DRAIN = "DRAIN"  # Shutdown after current tasks complete (Not yet implemented)
    ERROR = "ERROR"  # System-level critical error


@dataclass(frozen=True)
class SystemControlToken:
    command: ControlCommand
    payload: Any = None
