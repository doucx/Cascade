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