简要回答:
抱歉，我在之前的指令块中漏掉了 `old_string`。现在我补全完整的 `patch_file` 操作，确保包含路径、旧代码块和新代码块三个部分，以修复 Cache 异步化导致的测试失败。

## [WIP] fix(tests): 补全 Cache 异步化测试修复指令

### 错误分析
之前的 `patch_file` 指令格式不正确（缺少 `old_string` 参数），导致执行器报错。现在重新生成符合规范的补全计划。

### 用户需求
补全之前失败的 `patch_file` 指令，修复测试。

### 评论
必须严格遵守 Quipu 协议的围栏语法。测试修复完成后，所有的 Cache 操作将完全符合异步执行模型。

### 目标
1.  修复 `test_in_memory.py` 及其 `old_string` 匹配。
2.  修复 `test_redis_cache.py` 及其 `old_string` 匹配。
3.  优化 `test_engine_constraints.py` 的竞争条件逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #ai/instruct #task/domain/testing #task/object/cache-tests #task/action/async-fix #task/state/continue

---

### Script

#### Acts 1: 修复 InMemoryCacheBackend 测试

由于需要添加 `import pytest` 并修改所有函数，使用 `write_file` 更为稳健。

~~~~~act
write_file
tests/cascade-runtime/adapters/cache/test_in_memory.py
~~~~~
~~~~~python
import pytest
from unittest.mock import patch
from cascade.adapters.cache.in_memory import InMemoryCacheBackend

@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test basic set and get functionality."""
    cache = InMemoryCacheBackend()
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"


@pytest.mark.asyncio
async def test_cache_get_non_existent_key():
    """Test that getting a non-existent key returns None."""
    cache = InMemoryCacheBackend()
    assert await cache.get("non_existent") is None


@pytest.mark.asyncio
async def test_cache_set_overwrite():
    """Test that setting an existing key overwrites the value."""
    cache = InMemoryCacheBackend()
    await cache.set("key1", "value1")
    await cache.set("key1", "value2")
    assert await cache.get("key1") == "value2"


@pytest.mark.asyncio
async def test_cache_ttl_not_expired():
    """Test that a key can be retrieved before its TTL expires."""
    cache = InMemoryCacheBackend()
    with patch("time.time", return_value=1000):
        await cache.set("key_ttl", "value_ttl", ttl=60)

    with patch("time.time", return_value=1059):
        assert await cache.get("key_ttl") == "value_ttl"


@pytest.mark.asyncio
async def test_cache_ttl_expired():
    """Test that a key returns None after its TTL expires."""
    cache = InMemoryCacheBackend()
    with patch("time.time", return_value=1000):
        await cache.set("key_ttl", "value_ttl", ttl=60)

    # Move time forward to just after the expiry
    with patch("time.time", return_value=1061):
        assert await cache.get("key_ttl") is None

    # Verify that the key was actually removed from the store
    assert "key_ttl" not in cache._store
    assert "key_ttl" not in cache._expiry
~~~~~

#### Acts 2: 修复 RedisCacheBackend 测试

~~~~~act
write_file
tests/cascade-runtime/adapters/cache/test_redis_cache.py
~~~~~
~~~~~python
import pickle
import pytest
import asyncio
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
~~~~~

#### Acts 3: 修复 Engine 约束测试的时序问题

使用正确的三参数 `patch_file` 格式。

~~~~~act
patch_file
tests/cascade-runtime/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    # 2. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for 'task_a' to finish. This ensures the engine is ready for 'task_b'.
    await wait_for_task_finish(spy, "task_a")

    # 4. Inject a PAUSE command specifically for 'task_b'
    pause_scope = "task:task_b"
    pause_payload = {
        "id": "pause-b",
        "scope": pause_scope,
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", pause_payload
    )

    # 5. Wait briefly and assert that 'task_b' has NOT started
    await asyncio.sleep(0.2)
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "'task_b' started despite pause constraint"
~~~~~
~~~~~python
    # 2. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 3. Wait for 'task_a' to START (instead of finish).
    # This allows us to inject the constraint while A is running.
    await wait_for_task_start(spy, "task_a")

    # 4. Inject a PAUSE command specifically for 'task_b'
    pause_scope = "task:task_b"
    pause_payload = {
        "id": "pause-b",
        "scope": pause_scope,
        "type": "pause",
        "params": {},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", pause_payload
    )

    # Wait for A to finish naturally
    await wait_for_task_finish(spy, "task_a")

    # 5. Wait briefly and assert that 'task_b' has NOT started
    # Give the engine a moment to potentially (incorrectly) schedule B
    await asyncio.sleep(0.2)
    started_tasks = {e.task_name for e in spy.events_of_type(TaskExecutionStarted)}
    assert "task_b" not in started_tasks, "'task_b' started despite pause constraint"
~~~~~
