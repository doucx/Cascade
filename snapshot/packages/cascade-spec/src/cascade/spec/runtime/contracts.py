from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..physical.nodes import Token
from ..physical.object import Ref


@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_args: list[Ref]
    input_kwargs: dict[str, Ref]
    reply_to_nid: str
    trace: dict[str, Any]


@dataclass(frozen=True)
class DelayRequest:
    delay_seconds: float
    target_nid: str
    token: Token
