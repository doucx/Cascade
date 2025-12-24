import asyncio
from typing import Any, Dict, Optional


class InMemoryStateBackend:
    """
    An in-memory implementation of the StateBackend protocol using Python dictionaries.
    This is the default backend for local, single-process runs.
    """

    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, node_id: str, result: Any) -> None:
        await asyncio.to_thread(self._results.__setitem__, node_id, result)

    async def get_result(self, node_id: str) -> Optional[Any]:
        return await asyncio.to_thread(self._results.get, node_id)

    async def has_result(self, node_id: str) -> bool:
        return await asyncio.to_thread(self._results.__contains__, node_id)

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        await asyncio.to_thread(self._skipped.__setitem__, node_id, reason)

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        return await asyncio.to_thread(self._skipped.get, node_id)

    async def clear(self) -> None:
        """
        Clears all results and skip reasons. Used between TCO iterations.
        """
        await asyncio.to_thread(self._results.clear)
        await asyncio.to_thread(self._skipped.clear)