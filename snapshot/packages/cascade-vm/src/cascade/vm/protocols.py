from typing import Protocol, Callable, Awaitable, Any, Dict
from cascade.spec.physics import Token

class ReactorProtocol(Protocol):
    """
    Protocol defining the interface for a Cascade Reactor.
    This allows swapping the Python implementation with a Rust-based one.
    """
    active_task_count: int

    def prime(self) -> None:
        """Inject initial potential energy into the system."""
        ...

    async def step(self) -> int:
        """
        Perform one reaction step.
        Returns the number of tasks fired.
        """
        ...

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None:
        """Register a callback to receive tokens emitted by a specific port."""
        ...