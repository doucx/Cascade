import pickle
from typing import Any, Optional
from cascade.interfaces.protocols import StateBackend

try:
    import redis
except ImportError:
    redis = None


class RedisStateBackend:
    """
    A StateBackend implementation that persists results to Redis.
    """

    def __init__(self, run_id: str, client: "redis.Redis", ttl: int = 86400):
        if redis is None:
            raise ImportError("The 'redis' library is required to use RedisStateBackend.")
        
        self._run_id = run_id
        self._client = client
        self._ttl = ttl
        
        # Keys
        self._results_key = f"cascade:run:{run_id}:results"
        self._skipped_key = f"cascade:run:{run_id}:skipped"

    def put_result(self, node_id: str, result: Any) -> None:
        data = pickle.dumps(result)
        # Use a pipeline to set data and ensure expiry is set
        pipe = self._client.pipeline()
        pipe.hset(self._results_key, node_id, data)
        pipe.expire(self._results_key, self._ttl)
        pipe.execute()

    def get_result(self, node_id: str) -> Optional[Any]:
        data = self._client.hget(self._results_key, node_id)
        if data is None:
            return None
        return pickle.loads(data)

    def has_result(self, node_id: str) -> bool:
        return self._client.hexists(self._results_key, node_id)

    def mark_skipped(self, node_id: str, reason: str) -> None:
        pipe = self._client.pipeline()
        pipe.hset(self._skipped_key, node_id, reason)
        pipe.expire(self._skipped_key, self._ttl)
        pipe.execute()

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = self._client.hget(self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None