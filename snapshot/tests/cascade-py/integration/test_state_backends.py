import pytest
from unittest.mock import MagicMock, patch

import cascade as cs

# A simple task for testing
@cs.task
def add(a, b):
    return a + b

@cs.task
def identity(x):
    return x

def test_run_with_redis_backend_uri(monkeypatch):
    """
    Tests that cs.run with a redis:// URI correctly uses the RedisStateBackend.
    """
    # 1. Mock the redis library at the source where it's imported
    mock_redis_client = MagicMock()
    mock_redis_from_url = MagicMock(return_value=mock_redis_client)
    
    # We create a mock 'redis' module
    mock_redis_module = MagicMock()
    mock_redis_module.from_url = mock_redis_from_url
    
    # We patch it inside the cascade.__init__ where `_create_state_backend_factory` is.
    monkeypatch.setitem(__import__("sys").modules, "redis", mock_redis_module)

    # We also need to patch the import within the redis state adapter itself
    from cascade.adapters.state import redis as redis_state_module
    monkeypatch.setattr(redis_state_module, "redis", mock_redis_module)
    
    # 2. Define a simple workflow
    workflow = add(1, 2)
    
    # 3. Run the workflow
    cs.run(workflow, state_backend="redis://localhost:6379/0")
    
    # 4. Assertions
    # Was the redis client created from the URI?
    mock_redis_from_url.assert_called_once_with("redis://localhost:6379/0")
    
    # Did the backend try to save the result of the 'add' task?
    # We expect hset to be called.
    assert mock_redis_client.pipeline.return_value.hset.called
    # Check the call arguments (we can be more specific if needed)
    args, kwargs = mock_redis_client.pipeline.return_value.hset.call_args
    assert "results" in args[0]  # Check if it's the results key
    assert len(args) == 3 # key, field, value


def test_run_with_redis_backend_raises_if_not_installed(monkeypatch):
    """
    Ensures cs.run raises ImportError if redis is requested but not installed.
    """
    # Simulate redis not being installed by making the import fail
    monkeypatch.setitem(__import__("sys").modules, "redis", None)
    
    workflow = identity(1)
    
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        cs.run(workflow, state_backend="redis://localhost")