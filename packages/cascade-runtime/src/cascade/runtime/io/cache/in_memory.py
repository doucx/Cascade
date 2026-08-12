from __future__ import annotations

import time
from typing import Any


class InMemoryCacheBackend:
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}

    async def get(self, key: str) -> Any | None:
        if key in self._expiry and time.time() > self._expiry[key]:
            del self._store[key]
            del self._expiry[key]
            return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._store[key] = value
        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]
