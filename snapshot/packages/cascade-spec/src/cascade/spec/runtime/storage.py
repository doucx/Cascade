from __future__ import annotations

from typing import Any, Protocol

from ..physical.object import Ref


class ObjectStore(Protocol):
    def put(self, obj: Any, metadata: dict[str, Any] | None = None) -> Ref: ...

    def get(self, ref: Ref) -> Any: ...

    def peek(self, ref: Ref) -> Ref: ...

    def delete(self, ref: Ref) -> None: ...
