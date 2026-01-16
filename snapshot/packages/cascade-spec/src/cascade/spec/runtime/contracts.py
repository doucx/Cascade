from dataclasses import dataclass, field
from typing import Dict, Any

from ..physical.object import Ref
from ..physical.nodes import Token


@dataclass(frozen=True)
class ComputeRequest:
    """A request sent from the VM's dispatcher to a ComputeService."""

    code_hash: str
    input_refs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DelayRequest:
    """A request sent from a 'sleep' IC to the ChronosService."""

    delay_seconds: float
    target_nid: str
    token: Token