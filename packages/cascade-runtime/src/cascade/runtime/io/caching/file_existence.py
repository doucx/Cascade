from __future__ import annotations

import os
from typing import Any, Callable


class FileExistenceCache:
    def __init__(self, target_path: str | Callable[[dict[str, Any]], str]):
        self.target_path = target_path

    def _resolve_path(self, inputs: dict[str, Any]) -> str:
        if callable(self.target_path):
            return self.target_path(inputs)
        return str(self.target_path)

    async def check(self, task_id: str, inputs: dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    async def save(self, task_id: str, inputs: dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass
