from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SystemControlToken:
    """
    A special token that signals a lifecycle control command to the VM/Reactor.
    It is NOT a data token and should be handled by a special system bus.
    """
    command: str
    payload: Any = None