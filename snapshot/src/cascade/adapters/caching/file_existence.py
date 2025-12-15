import os
from typing import Any, Dict, Callable, Union
from cascade.runtime.protocols import CachePolicy

class FileExistenceCache:
    """
    A simple cache policy that considers a task 'cached' if a specific file exists.
    """

    def __init__(self, target_path: Union[str, Callable[[Dict[str, Any]], str]]):
        """
        Args:
            target_path: A string path or a function that accepts task inputs 
                         (args/kwargs dict) and returns a path string.
        """
        self.target_path = target_path

    def _resolve_path(self, inputs: Dict[str, Any]) -> str:
        if callable(self.target_path):
            return self.target_path(inputs)
        return str(self.target_path)

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass