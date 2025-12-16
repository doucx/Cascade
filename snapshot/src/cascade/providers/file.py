import asyncio
import os
import json
from typing import Any, Callable, Union
from dataclasses import dataclass

from cascade.spec.task import task, LazyResult
from cascade.providers import LazyFactory


# --- Core I/O Tasks (Synchronous functions run in separate thread) ---


@task(name="file_read_text")
async def _read_text_task(path: str, encoding: str) -> str:
    """Reads file content as a string."""

    def blocking_read():
        with open(path, "r", encoding=encoding) as f:
            return f.read()

    # Use asyncio.to_thread to run synchronous I/O without blocking the event loop
    return await asyncio.to_thread(blocking_read)


@task(name="file_read_bytes")
async def _read_bytes_task(path: str) -> bytes:
    """Reads file content as bytes."""

    def blocking_read():
        with open(path, "rb") as f:
            return f.read()

    return await asyncio.to_thread(blocking_read)


@task(name="file_exists")
async def _exists_task(path: str) -> bool:
    """Checks if the file exists."""
    return await asyncio.to_thread(os.path.exists, path)


@task(name="file_parse_json")
def _json_parse_task(text_content: str) -> Any:
    """Synchronously parses a JSON string."""
    return json.loads(text_content)


# --- File Factory (The object returned by cs.file) ---


@dataclass
class FileLazyFactory(LazyFactory):
    """
    Intermediate factory for cs.file(path) that returns a LazyResult
    when an I/O method is called.
    """

    path: Union[str, LazyResult]

    def read_text(self, encoding: str = "utf-8") -> LazyResult[str]:
        """Returns a LazyResult for reading the file content as text."""
        return _read_text_task(path=self.path, encoding=encoding)

    def read_bytes(self) -> LazyResult[bytes]:
        """Returns a LazyResult for reading the file content as bytes."""
        return _read_bytes_task(path=self.path)

    def exists(self) -> LazyResult[bool]:
        """Returns a LazyResult for checking file existence."""
        return _exists_task(path=self.path)

    def json(self, encoding: str = "utf-8") -> LazyResult[Any]:
        """Returns a LazyResult for reading the file content and parsing it as JSON."""
        # Chain the result: Read text -> Parse JSON
        text_result = self.read_text(encoding=encoding)
        return _json_parse_task(text_content=text_result)


# --- Provider Definition ---


class FileProvider:
    name = "file"

    def create_factory(self) -> Callable[[Union[str, LazyResult]], FileLazyFactory]:
        # The factory function (cs.file) simply wraps the path in the FileLazyFactory
        def factory_func(path: Union[str, LazyResult]) -> FileLazyFactory:
            return FileLazyFactory(path=path)

        return factory_func
