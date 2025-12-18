import asyncio
import os
from typing import Any, Union
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider

# --- Async IO Tasks ---

@task(name="read_text")
async def _read_text_task(path: str, encoding: str = "utf-8") -> str:
    def blocking_read():
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    return await asyncio.to_thread(blocking_read)

@task(name="read_bytes")
async def _read_bytes_task(path: str) -> bytes:
    def blocking_read():
        with open(path, "rb") as f:
            return f.read()
    return await asyncio.to_thread(blocking_read)

@task(name="write_text")
async def _write_text_task(path: str, content: str, encoding: str = "utf-8") -> None:
    def blocking_write():
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
    await asyncio.to_thread(blocking_write)

@task(name="write_bytes")
async def _write_bytes_task(path: str, content: bytes) -> None:
    def blocking_write():
        with open(path, "wb") as f:
            f.write(content)
    await asyncio.to_thread(blocking_write)

@task(name="fs_exists")
async def _exists_task(path: str) -> bool:
    return await asyncio.to_thread(os.path.exists, path)

# --- Providers ---

class ReadTextProvider(Provider):
    name = "read.text"
    def create_factory(self) -> LazyFactory:
        return _read_text_task

class ReadBytesProvider(Provider):
    name = "read.bytes"
    def create_factory(self) -> LazyFactory:
        return _read_bytes_task

class WriteTextProvider(Provider):
    name = "write.text"
    def create_factory(self) -> LazyFactory:
        return _write_text_task

class WriteBytesProvider(Provider):
    name = "write.bytes"
    def create_factory(self) -> LazyFactory:
        return _write_bytes_task

class FsExistsProvider(Provider):
    name = "fs.exists"
    def create_factory(self) -> LazyFactory:
        return _exists_task

# --- New io.local.* Aliases ---

class IoLocalReadTextProvider(ReadTextProvider):
    name = "io.local.read_text"

class IoLocalReadBytesProvider(ReadBytesProvider):
    name = "io.local.read_bytes"

class IoLocalWriteTextProvider(WriteTextProvider):
    name = "io.local.write_text"

class IoLocalWriteBytesProvider(WriteBytesProvider):
    name = "io.local.write_bytes"

class IoLocalExistsProvider(FsExistsProvider):
    name = "io.local.exists"