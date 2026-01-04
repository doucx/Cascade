from typing import Protocol, Callable, Awaitable
from cascade.spec.physics import Token


from typing import Protocol, Callable, Awaitable, Dict, Any, Optional
from cascade.spec.physics import Token


class ReactorProtocol(Protocol):
    active_task_count: int

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    async def step(self) -> int: ...

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None: ...
