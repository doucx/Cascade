import asyncio
import pickle
from typing import Any, Optional

try:
    import redis
except ImportError:
    redis = None


class RedisCacheBackend:
    """
    A CacheBackend implementation using Redis.
    Uses asyncio.to_thread to wrap synchronous redis client calls to ensure
    compatibility with the async Protocol without blocking the loop.
    """

    def __init__(self, client: "redis.Redis", prefix: str = "cascade:cache:"):
        if redis is None:
            raise ImportError(
                "The 'redis' library is required to use RedisCacheBackend."
            )
        self._client = client
        self._prefix = prefix

    async def get(self, key: str) -> Optional[Any]:
        def _blocking_get():
            data = self._client.get(self._prefix + key)
            if data is None:
                return None
            return pickle.loads(data)

        return await asyncio.to_thread(_blocking_get)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        def _blocking_set():
            data = pickle.dumps(value)
            self._client.set(self._prefix + key, data, ex=ttl)

        await asyncio.to_thread(_blocking_set)
