import asyncio
from typing import Protocol, Dict, Any, Optional


class ComputeServiceProtocol(Protocol):
    @property
    def active_count(self) -> int: ...

    def is_idle(self) -> bool: ...

    async def run(self) -> None: ...

    def stop(self) -> None: ...


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    def step(self) -> int: ...