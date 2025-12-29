import sys
import asyncio
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


# --- Tasks ---


@task(name="stdout_write")
async def _stdout_write_task(text: str) -> None:
    def blocking_write():
        # Using print ensures newline handling consistent with user expectations.
        print(text, file=sys.stdout)
        sys.stdout.flush()

    await asyncio.to_thread(blocking_write)


@task(name="stdin_read_line")
async def _stdin_read_line_task(*_args) -> str:
    def blocking_read():
        return sys.stdin.readline().strip()

    return await asyncio.to_thread(blocking_read)


# --- Providers ---


class StdOutWriteProvider(Provider):
    name = "io.stdout.write"

    def create_factory(self) -> LazyFactory:
        return _stdout_write_task


class StdInReadLineProvider(Provider):
    name = "io.stdin.read_line"

    def create_factory(self) -> LazyFactory:
        return _stdin_read_line_task
