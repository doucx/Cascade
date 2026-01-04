from typing import Dict, Callable, Any

# A generic callable type for task functions
TaskCallable = Callable[..., Any]


class CodeRegistry:
    """
    The runtime registry for executable code.
    It maps canonical code structure hashes to actual Python callables.
    """

    def __init__(self):
        self._registry: Dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        """
        Registers a function under its canonical hash.
        If the hash already exists, we assume the code is identical (idempotent).
        """
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        """
        Retrieves a function by its canonical hash.
        Raises KeyError if not found.
        """
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry