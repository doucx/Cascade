from typing import Any, Dict, Optional


class InMemoryStateBackend:
    """
    An in-memory implementation of the StateBackend protocol using Python dictionaries.
    This is the default backend for local, single-process runs.

    ARCHITECTURAL NOTE on ASYNC IMPLEMENTATION:
    This class adheres to the `async def` contract of the StateBackend protocol,
    but it does NOT use `asyncio.to_thread`. This is an intentional performance
    optimization.

    Dictionary operations are synchronous but are pure-CPU and extremely fast
    (nanosecond-scale). They do not perform blocking I/O. Using `to_thread`
    would introduce significant overhead (context switching, thread pool management)
    for a non-existent problem, crippling performance in high-throughput scenarios
    like TCO fast paths.

    This implementation provides a compliant async interface with minimal overhead,
    making it suitable for its primary role as a high-performance, single-process backend.
    """

    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, node_id: str, result: Any) -> None:
        self._results[node_id] = result

    async def get_result(self, node_id: str) -> Optional[Any]:
        return self._results.get(node_id)

    async def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        self._skipped[node_id] = reason

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)

    async def clear(self) -> None:
        """
        Clears all results and skip reasons. Used between TCO iterations.
        """
        self._results.clear()
        self._skipped.clear()
