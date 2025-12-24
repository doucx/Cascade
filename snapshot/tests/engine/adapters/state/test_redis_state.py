import pickle
import pytest
from unittest.mock import MagicMock, AsyncMock

# We import the module to patch its members
from cascade.adapters.state import redis as redis_state_module


@pytest.fixture
def mock_redis_client():
    """Provides a MagicMock for the redis.Redis client."""
    mock_client = MagicMock()
    # Mock the pipeline context manager
    mock_pipeline = MagicMock()
    mock_client.pipeline.return_value = mock_pipeline
    return mock_client, mock_pipeline


def test_redis_state_backend_dependency_check(monkeypatch):
    """
    Ensures RedisStateBackend raises ImportError if 'redis' is not installed.
    """
    monkeypatch.setattr(redis_state_module, "redis", None)
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        from cascade.adapters.state.redis import RedisStateBackend

        RedisStateBackend(run_id="test", client=MagicMock())


@pytest.mark.asyncio
async def test_put_result(mock_redis_client):
    """
    Verifies that put_result serializes data and calls Redis HSET and EXPIRE.
    """
    client, pipeline = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    test_result = {"status": "ok", "data": [1, 2]}
    await backend.put_result("node_a", test_result)

    expected_key = "cascade:run:run123:results"
    expected_data = pickle.dumps(test_result)

    client.pipeline.assert_called_once()
    pipeline.hset.assert_called_once_with(expected_key, "node_a", expected_data)
    pipeline.expire.assert_called_once_with(expected_key, 86400)
    pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_result(mock_redis_client):
    """
    Verifies that get_result retrieves and deserializes data correctly.
    """
    client, _ = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    # Case 1: Result found
    test_result = {"value": 42}
    pickled_result = pickle.dumps(test_result)
    client.hget.return_value = pickled_result

    result = await backend.get_result("node_b")

    client.hget.assert_called_once_with("cascade:run:run123:results", "node_b")
    assert result == test_result

    # Case 2: Result not found
    client.hget.return_value = None
    assert await backend.get_result("node_c") is None