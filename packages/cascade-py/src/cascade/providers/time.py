import asyncio
from typing import Union

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


@task(name="wait")
async def _wait_task(delay: Union[float, int]) -> None:
    """
    Asynchronously waits for a specified duration.
    This is a non-blocking operation.

    Args:
        delay: The duration to wait in seconds.
    """
    await asyncio.sleep(float(delay))


class TimeWaitProvider(Provider):
    name = "wait"

    def create_factory(self) -> LazyFactory:
        return _wait_task
