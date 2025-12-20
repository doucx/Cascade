import pickle
import pytest
from unittest.mock import MagicMock

from cascade.adapters.cache import redis as redis_cache_module


@pytest.fixture
def mock_redis_client():
    """Provides a MagicMock for the redis.Redis client."""
    return MagicMock()


def test_redis_cache_backend_dependency_check(monkeypatch):
    """
    Ensures RedisCacheBackend raises ImportError if 'redis' is not installed.
    """
    monkeypatch.setattr(redis_cache_module, "redis", None)
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        from cascade.adapters.cache.redis import RedisCacheBackend

        RedisCacheBackend(client=MagicMock())


@pytest.mark.asyncio
async def test_set_cache(mock_redis_client):
    """
    Verifies that set() serializes data and calls Redis SET with TTL.
    """
    backend = redis_cache_module.RedisCacheBackend(client=mock_redis_client)

    value = {"result": "cached"}
    await backend.set("cache_key_1", value, ttl=300)

    expected_key = "cascade:cache:cache_key_1"
    expected_data = pickle.dumps(value)

    mock_redis_client.set.assert_called_once_with(expected_key, expected_data, ex=300)


@pytest.mark.asyncio
async def test_get_cache(mock_redis_client):
    """
    Verifies that get() retrieves and deserializes data correctly.
    """
    backend = redis_cache_module.RedisCacheBackend(client=mock_redis_client)

    # Case 1: Cache hit
    value = {"result": "cached"}
    pickled_value = pickle.dumps(value)
    mock_redis_client.get.return_value = pickled_value

    result = await backend.get("cache_key_1")

    mock_redis_client.get.assert_called_once_with("cascade:cache:cache_key_1")
    assert result == value

    # Case 2: Cache miss
    mock_redis_client.get.return_value = None
    assert await backend.get("cache_key_2") is None
