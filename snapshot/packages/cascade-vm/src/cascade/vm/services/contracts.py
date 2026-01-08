from dataclasses import dataclass
from cascade.spec.physical.nodes import Token


@dataclass(frozen=True)
class DelayRequest:
    """
    A request sent to the ChronosService to delay a token.
    """

    delay_seconds: float
    target_nid: str
    token: Token