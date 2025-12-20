import asyncio
from typing import Optional, Any

from cascade.spec.task import task
from cascade.spec.resource import inject
from cascade.providers import LazyFactory, Provider
from cascade.interfaces.protocols import Connector


@task(name="recv")
async def _recv_task(
    topic: str,
    timeout: Optional[float] = None,
    # This is a special, undocumented resource provided by the Engine
    connector: Connector = inject("_internal_connector"),
) -> Any:
    """
    Pauses execution until a signal is received on the given topic.
    """
    if connector is None:
        raise RuntimeError(
            "cs.recv cannot be used because no Connector is configured in the Engine."
        )

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        # Ensure we only set the result once
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        # Re-raise to allow Cascade's error handling to catch it
        raise asyncio.TimeoutError(
            f"Timed out waiting for signal on topic '{topic}' after {timeout}s"
        )
    finally:
        # Crucially, unsubscribe to prevent resource leaks
        if subscription and hasattr(subscription, "unsubscribe"):
            await subscription.unsubscribe()


class RecvProvider(Provider):
    name = "recv"

    def create_factory(self) -> LazyFactory:
        return _recv_task
