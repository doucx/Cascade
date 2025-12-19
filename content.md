好的，我们来为 `RedisStateBackend` 和新的 `cs.run` 工厂逻辑创建测试。

我将遵循**“验证意图而非实现”**的原则，使用 `unittest.mock` 来模拟 `redis` 客户端。这确保了我们的测试是健壮的，并且不需要一个正在运行的 Redis 实例，使得测试套件在任何环境中都能可靠运行。

## [WIP] test(runtime): Add unit and integration tests for Redis backends

### 用户需求
为新实现的 `RedisStateBackend`、`RedisCacheBackend` 以及 `cs.run` 中的 URI 工厂逻辑编写测试。测试应使用 Mock 来模拟 Redis 依赖，以保证兼容性和可移植性。

### 评论
为新功能添加测试是至关重要的。通过 Mock Redis，我们可以精确地验证我们的适配器是否与 `redis-py` 库正确交互（例如，调用了正确的命令、使用了正确的键、并且正确地序列化/反序列化了数据），而无需依赖外部服务。

### 目标
1.  **单元测试**:
    *   创建一个新的测试文件 `tests/cascade-runtime/adapters/state/test_redis.py`，验证 `RedisStateBackend` 的核心逻辑。
    *   创建一个新的测试文件 `tests/cascade-runtime/adapters/cache/test_redis.py`，验证 `RedisCacheBackend` 的核心逻辑。
2.  **集成测试**:
    *   创建一个新的测试文件 `tests/cascade-py/integration/test_state_backends.py`，验证 `cs.run` 的 `state_backend="redis://..."` URI 解析和端到端流程。
3.  **依赖检查**: 确保在未安装 `redis` 库时，系统会抛出明确的 `ImportError`。

### 基本原理
我们将使用 `pytest` 的 `monkeypatch` fixture 来模拟 `redis` 模块的导入和 `redis.from_url` 等关键函数。然后，我们将注入一个 `MagicMock` 对象作为 Redis 客户端，并断言我们的代码是否以预期的方式调用了该 Mock 对象的方法。

### 标签
#intent/tooling #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/redis-backend #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 创建测试目录结构

首先，确保新的测试文件有存放的位置。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p tests/cascade-runtime/adapters/state
mkdir -p tests/cascade-runtime/adapters/cache
mkdir -p tests/cascade-py/integration
~~~~~

#### Acts 2: 编写 `RedisStateBackend` 的单元测试

这个测试文件将隔离验证 `RedisStateBackend` 的行为。

~~~~~act
write_file
tests/cascade-runtime/adapters/state/test_redis.py
~~~~~
~~~~~python
import pickle
import pytest
from unittest.mock import MagicMock, patch

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


def test_redis_backend_dependency_check(monkeypatch):
    """
    Ensures RedisStateBackend raises ImportError if 'redis' is not installed.
    """
    monkeypatch.setattr(redis_state_module, "redis", None)
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        from cascade.adapters.state.redis import RedisStateBackend
        RedisStateBackend(run_id="test", client=MagicMock())


def test_put_result(mock_redis_client):
    """
    Verifies that put_result serializes data and calls Redis HSET and EXPIRE.
    """
    client, pipeline = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)
    
    test_result = {"status": "ok", "data": [1, 2]}
    backend.put_result("node_a", test_result)

    expected_key = "cascade:run:run123:results"
    expected_data = pickle.dumps(test_result)

    client.pipeline.assert_called_once()
    pipeline.hset.assert_called_once_with(expected_key, "node_a", expected_data)
    pipeline.expire.assert_called_once_with(expected_key, 86400)
    pipeline.execute.assert_called_once()


def test_get_result(mock_redis_client):
    """
    Verifies that get_result retrieves and deserializes data correctly.
    """
    client, _ = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    # Case 1: Result found
    test_result = {"value": 42}
    pickled_result = pickle.dumps(test_result)
    client.hget.return_value = pickled_result
    
    result = backend.get_result("node_b")
    
    client.hget.assert_called_once_with("cascade:run:run123:results", "node_b")
    assert result == test_result

    # Case 2: Result not found
    client.hget.return_value = None
    assert backend.get_result("node_c") is None


def test_mark_skipped(mock_redis_client):
    """
    Verifies that mark_skipped calls HSET and EXPIRE on the skipped key.
    """
    client, pipeline = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    backend.mark_skipped("node_d", "ConditionFalse")
    
    expected_key = "cascade:run:run123:skipped"
    
    client.pipeline.assert_called_once()
    pipeline.hset.assert_called_once_with(expected_key, "node_d", "ConditionFalse")
    pipeline.expire.assert_called_once_with(expected_key, 86400)
    pipeline.execute.assert_called_once()
~~~~~

#### Acts 3: 编写 `RedisCacheBackend` 的单元测试

这个测试文件将隔离验证 `RedisCacheBackend` 的行为。

~~~~~act
write_file
tests/cascade-runtime/adapters/cache/test_redis.py
~~~~~
~~~~~python
import pickle
import pytest
from unittest.mock import MagicMock

from cascade.adapters.cache import redis as redis_cache_module

@pytest.fixture
def mock_redis_client():
    """Provides a MagicMock for the redis.Redis client."""
    return MagicMock()

def test_redis_cache_dependency_check(monkeypatch):
    """
    Ensures RedisCacheBackend raises ImportError if 'redis' is not installed.
    """
    monkeypatch.setattr(redis_cache_module, "redis", None)
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        from cascade.adapters.cache.redis import RedisCacheBackend
        RedisCacheBackend(client=MagicMock())

def test_set_cache(mock_redis_client):
    """
    Verifies that set() serializes data and calls Redis SET with TTL.
    """
    backend = redis_cache_module.RedisCacheBackend(client=mock_redis_client)
    
    value = {"result": "cached"}
    backend.set("cache_key_1", value, ttl=300)

    expected_key = "cascade:cache:cache_key_1"
    expected_data = pickle.dumps(value)

    mock_redis_client.set.assert_called_once_with(expected_key, expected_data, ex=300)

def test_get_cache(mock_redis_client):
    """
    Verifies that get() retrieves and deserializes data correctly.
    """
    backend = redis_cache_module.RedisCacheBackend(client=mock_redis_client)

    # Case 1: Cache hit
    value = {"result": "cached"}
    pickled_value = pickle.dumps(value)
    mock_redis_client.get.return_value = pickled_value

    result = backend.get("cache_key_1")
    
    mock_redis_client.get.assert_called_once_with("cascade:cache:cache_key_1")
    assert result == value

    # Case 2: Cache miss
    mock_redis_client.get.return_value = None
    assert backend.get("cache_key_2") is None
~~~~~

#### Acts 4: 编写 `cs.run` 的集成测试

这个测试将验证从 URI 解析到引擎执行的整个流程。

~~~~~act
write_file
tests/cascade-py/integration/test_state_backends.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
我们已经为 Redis 后端添加了必要的单元测试和集成测试。代码的健壮性得到了提升。

现在，我们可以放心地继续执行路线图的下一个里程碑了： **里程碑 5.2: 引入 IPFS 作为原生数据层**。这将解决在工作流中处理大型文件和数据的问题。
