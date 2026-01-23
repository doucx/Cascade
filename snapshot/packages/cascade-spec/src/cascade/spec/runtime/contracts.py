from dataclasses import dataclass
from typing import Dict, Any, List

from ..physical.object import Ref
from ..physical.nodes import Token


from ..physical.object import Ref
from ..physical.nodes import Token


@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_args: List[Ref]
    input_kwargs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any]


@dataclass(frozen=True)
class DelayRequest:
    delay_seconds: float
    target_nid: str
    token: Token
