import pickle
from typing import Any, Optional

try:
    import redis
except ImportError:
    redis = None


class RedisCacheBackend:
    """
    A CacheBackend implementation using Redis.
    """

    def __init__(self, client: "redis.Redis", prefix: str = "cascade:cache:"):
        if redis is None:
            raise ImportError("The 'redis' library is required to use RedisCacheBackend.")
        self._client = client
        self._prefix = prefix

    def get(self, key: str) -> Optional[Any]:
        data = self._client.get(self._prefix + key)
        if data is None:
            return None
        return pickle.loads(data)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        data = pickle.dumps(value)
        self._client.set(self._prefix + key, data, ex=ttl)