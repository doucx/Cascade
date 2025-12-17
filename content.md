Excellent, all tests are passing. This confirms that our recent refactoring of the `FlowManager` has successfully restored the core functionality while preserving the new state-decoupled architecture.

However, the coverage report you provided highlights one critical gap before we can create a commit. Our brand new `src/cascade/adapters/cache/in_memory.py` module has **0% test coverage**.

Committing a new, foundational component without any tests would introduce significant risk and violate our testing principles. Therefore, I will create one final `[WIP]` plan to add unit tests for `InMemoryCacheBackend`. Once these tests are passing, we will have a complete, robust, and verified set of changes ready for a clean commit.

## [WIP] test(cache): Add unit tests for InMemoryCacheBackend

### 用户需求
根据测试覆盖率报告，为新创建的 `InMemoryCacheBackend` 添加单元测试，以确保其功能正确性，为后续的提交做准备。

### 评论
这是一个必要的步骤。`InMemoryCacheBackend` 是我们新缓存架构的基石，虽然其逻辑简单，但包含时间敏感的 TTL (Time-To-Live) 功能，这是典型的需要通过测试来精确验证的边缘情况。添加这些测试将确保我们的缓存后端是可靠的。

### 目标
1.  创建新的测试文件 `tests/adapters/cache/test_in_memory.py`。
2.  实现单元测试，覆盖 `InMemoryCacheBackend` 的 `get`, `set` 和 TTL 过期逻辑。

### 基本原理
我们将编写一个标准的 `pytest` 测试套件：
- **基础功能**: 验证基本的 `set` 和 `get` 操作是否按预期工作。
- **TTL 功能**: 使用 `unittest.mock.patch` 来控制 `time.time()` 的返回值，从而精确地模拟时间的流逝，验证：
    1. 在 TTL 过期**前**调用 `get` 能成功返回值。
    2. 在 TTL 过期**后**调用 `get` 会返回 `None`，并且缓存项被正确清理。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/tests #concept/caching
#ai/instruct
#task/domain/testing #task/object/cache-backend #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: 创建 `InMemoryCacheBackend` 的测试文件

我们将创建并填充 `InMemoryCacheBackend` 的单元测试。

~~~~~act
write_file
tests/adapters/cache/test_in_memory.py
~~~~~
~~~~~python
import time
from unittest.mock import patch
from cascade.adapters.cache.in_memory import InMemoryCacheBackend


def test_cache_set_and_get():
    """Test basic set and get functionality."""
    cache = InMemoryCacheBackend()
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_get_non_existent_key():
    """Test that getting a non-existent key returns None."""
    cache = InMemoryCacheBackend()
    assert cache.get("non_existent") is None


def test_cache_set_overwrite():
    """Test that setting an existing key overwrites the value."""
    cache = InMemoryCacheBackend()
    cache.set("key1", "value1")
    cache.set("key1", "value2")
    assert cache.get("key1") == "value2"


def test_cache_ttl_not_expired():
    """Test that a key can be retrieved before its TTL expires."""
    cache = InMemoryCacheBackend()
    with patch('time.time', return_value=1000):
        cache.set("key_ttl", "value_ttl", ttl=60)

    with patch('time.time', return_value=1059):
        assert cache.get("key_ttl") == "value_ttl"


def test_cache_ttl_expired():
    """Test that a key returns None after its TTL expires."""
    cache = InMemoryCacheBackend()
    with patch('time.time', return_value=1000):
        cache.set("key_ttl", "value_ttl", ttl=60)

    # Move time forward to just after the expiry
    with patch('time.time', return_value=1061):
        assert cache.get("key_ttl") is None

    # Verify that the key was actually removed from the store
    assert "key_ttl" not in cache._store
    assert "key_ttl" not in cache._expiry
~~~~~

### 下一步建议
一旦这个计划执行完毕并通过测试，我们的代码库将处于一个非常健康的状态：所有核心重构已完成，所有回归问题已修复，并且所有新组件都拥有了基础的测试覆盖。届时，我们将可以自信地创建一个 `[COMMIT]` 计划来封装从引入 `StateBackend` 到现在的所有工作。
