from __future__ import annotations

import logging
from typing import Any, Callable

# A generic callable type for task functions
TaskCallable = Callable[..., Any]

logger = logging.getLogger(__name__)


class CodeRegistry:
    def __init__(self):
        self._registry: dict[str, TaskCallable] = {}

    def register(self, canonical_hash: str, func: TaskCallable) -> None:
        if (
            canonical_hash in self._registry
            and self._registry[canonical_hash] is not func
        ):
            logger.warning(
                f"Hash collision detected for '{canonical_hash}'. "
                f"Overwriting registration for '{self._registry[canonical_hash].__name__}' "
                f"with new function '{func.__name__}'."
            )
        self._registry[canonical_hash] = func

    def get(self, canonical_hash: str) -> TaskCallable:
        if canonical_hash not in self._registry:
            raise KeyError(f"Code for hash '{canonical_hash}' not found in registry.")
        return self._registry[canonical_hash]

    def has(self, canonical_hash: str) -> bool:
        return canonical_hash in self._registry
