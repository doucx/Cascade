from __future__ import annotations

import asyncio
from typing import Any, Protocol


class ComputeServiceProtocol(Protocol):
    @property
    def active_count(self) -> int: ...
    def is_idle(self) -> bool: ...
    async def run(self) -> None: ...
    def stop(self) -> None: ...


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: asyncio.Queue | None

    def prime(self, genesis_trace: dict[str, Any] | None = None) -> None: ...
    def step(self) -> int: ...
