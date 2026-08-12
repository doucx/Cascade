from __future__ import annotations

from typing import Any, Awaitable, Protocol

from ..physical.object import Ref


class ComputeDelegate(Protocol):
    def submit(
        self, code_hash: str, input_refs: dict[str, Ref], config: dict[str, Any]
    ) -> Awaitable[Ref]: ...
