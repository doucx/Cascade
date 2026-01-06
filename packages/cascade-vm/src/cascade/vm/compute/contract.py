from dataclasses import dataclass, field
from typing import Dict, Any

from cascade.spec.physical.object import Ref


@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str

    input_refs: Dict[str, Ref]

    reply_to_nid: str

    trace: Dict[str, Any] = field(default_factory=dict)
