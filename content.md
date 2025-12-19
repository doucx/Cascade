好的，我分析了错误。`TypeError: a bytes-like object is required, not 'MagicMock'` 这个错误非常明确，它发生在 `pickle.loads()` 尝试反序列化一个 `MagicMock` 对象时，而不是预期的 `bytes` 对象。

### 错误分析

1.  **发生点**: 错误发生在 `RedisStateBackend.get_result()` 内部的 `pickle.loads(data)` 调用。
2.  **根本原因**: 在我们的集成测试 `test_run_with_redis_backend_uri` 中，我们模拟了 `redis.from_url()`，使其返回一个 `mock_redis_client` (`MagicMock`)。然而，我们没有配置这个 mock 的 `hget` 方法的行为。
3.  **执行流程**:
    *   `cs.run(workflow)` 成功执行了 `add(1, 2)` 任务。
    *   `Engine` 调用 `RedisStateBackend.put_result()`，将 `pickle.dumps(3)`（一个 `bytes` 对象）存入 mock 的 `hset` 中。
    *   在工作流的最后，`Engine` 需要返回最终结果，因此它调用 `RedisStateBackend.get_result()` 来获取目标任务 (`add` 任务) 的结果。
    *   `get_result()` 调用 `self._client.hget(...)`。由于 `hget` 没有被配置，它默认返回一个新的 `MagicMock` 对象。
    *   这个 `MagicMock` 对象被传递给 `pickle.loads()`，导致了 `TypeError`。

### 解决方案

我们需要让我们的 mock Redis 客户端变得更“智能”，让它能够模拟存取行为。我们将创建一个简单的内存字典来充当 Redis 的存储，并配置 mock 的 `hset` 和 `hget` 方法来操作这个字典。

## [WIP] fix(tests): Create stateful mock for Redis client in integration tests

### 用户需求
修复集成测试中的 `TypeError`，通过创建一个有状态的 Redis mock 来确保 `hget` 返回 `hset` 存入的字节数据，而不是一个 `MagicMock`。

### 评论
这是一个经典的 mock 陷阱。无状态的 mock 只能验证“调用”，但无法模拟“交互”。通过添加一个简单的内存存储，我们的 mock 可以正确模拟 `put`/`get` 循环，使测试更真实、更健壮。

### 目标
1.  修改 `tests/cascade-py/integration/test_state_backends.py` 中的 mock 设置。
2.  为 `mock_redis_client` 和其 pipeline 添加 `side_effect`，使其 `hset`, `hget`, `hexists` 和 `expire` 方法能与一个共享字典交互。
3.  在测试中增加对 `cs.run` 返回值的断言，以验证整个存取周期。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/mocking #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复集成测试

我们将重写 `test_state_backends.py` 以使用有状态的 mock。

~~~~~act
patch_file
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
~~~~~
~~~~~python
import pickle
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
    
    # The key of the hash field is the node's UUID
    node_uuid = workflow._uuid
    stored_pickled_data = store[results_key][node_uuid]
    
    # Verify the stored data is correct
    assert pickle.loads(stored_pickled_data) == 3
~~~~~

### 下一步建议
通过创建这个有状态的 mock，我们不仅修复了 `TypeError`，还极大地增强了集成测试的验证能力。现在我们可以确信 `RedisStateBackend` 的序列化和反序列化逻辑与 `Engine` 的执行周期正确集成。

现在，测试应该可以通过了。我建议我们正式进入**里程碑 5.2: 引入 IPFS 作为原生数据层**。
