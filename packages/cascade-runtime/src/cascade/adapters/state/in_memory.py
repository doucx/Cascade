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

    def put_result(self, node_id: str, result: Any) -> None:
        self._results[node_id] = result

    def get_result(self, node_id: str) -> Optional[Any]:
        return self._results.get(node_id)

    def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    def mark_skipped(self, node_id: str, reason: str) -> None:
        self._skipped[node_id] = reason

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)

    def clear(self) -> None:
        """Clears all stored state. Used for garbage collection between TCO steps."""
        self._results.clear()
        self._skipped.clear()
