import os
from typing import Any, Dict, Callable, Union


class FileExistenceCache:
    def __init__(self, target_path: Union[str, Callable[[Dict[str, Any]], str]]):
        self.target_path = target_path

    def _resolve_path(self, inputs: Dict[str, Any]) -> str:
        if callable(self.target_path):
            return self.target_path(inputs)
        return str(self.target_path)

    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass
