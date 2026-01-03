from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SystemControlToken:
    command: str
    payload: Any = None
