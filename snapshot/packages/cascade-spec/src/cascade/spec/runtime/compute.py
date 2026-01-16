from typing import Protocol, Dict, Awaitable, Any
from ..physical.object import Ref


class ComputeDelegate(Protocol):
    def submit(
        self, code_hash: str, input_refs: Dict[str, Ref], config: Dict[str, Any]
    ) -> Awaitable[Ref]: ...
