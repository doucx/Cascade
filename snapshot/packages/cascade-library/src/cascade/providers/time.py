from __future__ import annotations

import asyncio

from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider


@task(name="wait")
async def _wait_task(delay: float) -> None:
    await asyncio.sleep(float(delay))


class TimeWaitProvider(Provider):
    name = "wait"

    def create_factory(self) -> LazyFactory:
        return _wait_task
