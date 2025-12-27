from typing import Any, Dict, Optional
import time


class InMemoryCacheBackend:
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    async def get(self, key: str) -> Optional[Any]:
        if key in self._expiry:
            if time.time() > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = value
        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]
