from typing import Any, Dict, Optional


class InMemoryStateBackend:
    def __init__(self, current_run_id: str):
        self._current_run_id = current_run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, current_node_instance_hash: str, result: Any) -> None:
        self._results[current_node_instance_hash] = result

    async def get_result(self, current_node_instance_hash: str) -> Optional[Any]:
        return self._results.get(current_node_instance_hash)

    async def has_result(self, current_node_instance_hash: str) -> bool:
        return current_node_instance_hash in self._results

    async def mark_skipped(self, current_node_instance_hash: str, reason: str) -> None:
        self._skipped[current_node_instance_hash] = reason

    async def get_skip_reason(self, current_node_instance_hash: str) -> Optional[str]:
        return self._skipped.get(current_node_instance_hash)

    async def clear(self) -> None:
        self._results.clear()
        self._skipped.clear()
