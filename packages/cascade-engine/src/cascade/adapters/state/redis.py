import asyncio
import pickle
from typing import Any, Optional

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
            raise ImportError(
                "The 'redis' library is required to use RedisStateBackend."
            )

        self._run_id = run_id
        self._client = client
        self._ttl = ttl

        # Keys
        self._results_key = f"cascade:run:{run_id}:results"
        self._skipped_key = f"cascade:run:{run_id}:skipped"

    async def put_result(self, node_id: str, result: Any) -> None:
        data = pickle.dumps(result)
        await asyncio.to_thread(self._sync_put, node_id, data)

    def _sync_put(self, node_id: str, data: bytes):
        pipe = self._client.pipeline()
        pipe.hset(self._results_key, node_id, data)
        pipe.expire(self._results_key, self._ttl)
        pipe.execute()

    async def get_result(self, node_id: str) -> Optional[Any]:
        data = await asyncio.to_thread(self._client.hget, self._results_key, node_id)
        if data is None:
            return None
        return pickle.loads(data)

    async def has_result(self, node_id: str) -> bool:
        return await asyncio.to_thread(self._client.hexists, self._results_key, node_id)

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        await asyncio.to_thread(self._sync_mark_skipped, node_id, reason)

    def _sync_mark_skipped(self, node_id: str, reason: str):
        pipe = self._client.pipeline()
        pipe.hset(self._skipped_key, node_id, reason)
        pipe.expire(self._skipped_key, self._ttl)
        pipe.execute()

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = await asyncio.to_thread(self._client.hget, self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None

    async def clear(self) -> None:
        """
        Clears the state for the current run.
        For Redis, since TCO reuses the same run_id and overwrites keys,
        explicit clearing might be expensive (SCAN+DEL).
        For now, we treat this as a no-op to satisfy the protocol,
        relying on key overwrite semantics.
        """
        pass
