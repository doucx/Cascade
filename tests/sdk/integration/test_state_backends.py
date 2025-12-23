import pickle
import pytest
from unittest.mock import MagicMock

import cascade as cs


# A simple task for testing
@cs.task
def add(a, b):
    return a + b


@cs.task
def identity(x):
    return x


@pytest.fixture
def stateful_redis_mock(monkeypatch):
    """
    A fixture that provides a stateful mock for the redis client,
    simulating hset/hget operations with an in-memory dictionary.
    """
    mock_store = {}

    def mock_hset(name, key, value):
        if name not in mock_store:
            mock_store[name] = {}
        mock_store[name][key] = value
        # hset in redis-py returns 1 if new field, 0 if updated. Mocking 1 is fine.
        return 1

    def mock_hget(name, key):
        return mock_store.get(name, {}).get(key)

    def mock_hexists(name, key):
        return key in mock_store.get(name, {})

    mock_client = MagicMock()
    mock_pipeline = MagicMock()

    # Configure the pipeline methods
    mock_pipeline.hset.side_effect = mock_hset
    mock_pipeline.expire.return_value = None
    mock_pipeline.execute.return_value = []

    # Configure the client methods
    mock_client.hget.side_effect = mock_hget
    mock_client.hexists.side_effect = mock_hexists
    mock_client.pipeline.return_value = mock_pipeline

    mock_redis_from_url = MagicMock(return_value=mock_client)

    mock_redis_module = MagicMock()
    mock_redis_module.from_url = mock_redis_from_url

    # Patch the redis module in all necessary locations
    monkeypatch.setitem(__import__("sys").modules, "redis", mock_redis_module)
    from cascade.adapters.state import redis as redis_state_module

    monkeypatch.setattr(redis_state_module, "redis", mock_redis_module)
    from cascade.adapters.cache import redis as redis_cache_module

    monkeypatch.setattr(redis_cache_module, "redis", mock_redis_module)

    # Yield the mocks and the store for assertions
    return {
        "from_url": mock_redis_from_url,
        "client": mock_client,
        "pipeline": mock_pipeline,
        "store": mock_store,
    }


def test_run_with_redis_backend_uri(stateful_redis_mock):
    """
    Tests that cs.run with a redis:// URI correctly uses the RedisStateBackend
    and that the put/get cycle for the final result is successful.
    """
    # 1. Define a simple workflow
    workflow = add(1, 2)

    # 2. Run the workflow
    result = cs.run(workflow, state_backend="redis://localhost:6379/0")

    # 3. Assertions
    # Was the redis client created from the URI?
    stateful_redis_mock["from_url"].assert_called_once_with("redis://localhost:6379/0")

    # Was the result correctly calculated and returned?
    assert result == 3

    # Did the backend try to save the result of the 'add' task?
    stateful_redis_mock["pipeline"].hset.assert_called()

    # Verify the content in the mock store
    store = stateful_redis_mock["store"]
    # Find the results hash in the store (key contains the run_id, so we search)
    results_key = next((k for k in store if "results" in k), None)
    assert results_key is not None

    from cascade.graph.build import build_graph

    # The key of the hash field is the node's CANONICAL ID, not its instance UUID
    _, instance_map = build_graph(workflow)
    node = instance_map[workflow._uuid]

    stored_pickled_data = store[results_key][node.id]

    # Verify the stored data is correct
    assert pickle.loads(stored_pickled_data) == 3


def test_run_with_redis_backend_raises_if_not_installed(monkeypatch):
    """
    Ensures cs.run raises ImportError if redis is requested but not installed.
    """
    # Simulate redis not being installed by making the import fail
    monkeypatch.setitem(__import__("sys").modules, "redis", None)

    workflow = identity(1)

    with pytest.raises(ImportError, match="The 'redis' library is required"):
        cs.run(workflow, state_backend="redis://localhost")
