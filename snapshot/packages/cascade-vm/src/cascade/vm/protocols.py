import asyncio
from typing import Protocol, Callable, Awaitable, Dict, Any, Optional
from cascade.spec.physical.nodes import Token


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    def step(self) -> int: ...