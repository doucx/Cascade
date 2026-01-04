from typing import Dict, Callable, Any

# A generic callable type for task functions
TaskCallable = Callable[..., Any]


class CodeRegistry:
    def __init__(self):
        self._registry: Dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry
