from dataclasses import dataclass
from cascade.spec.physical.nodes import Token


@dataclass(frozen=True)
class DelayRequest:
    delay_seconds: float
    target_nid: str
    token: Token
