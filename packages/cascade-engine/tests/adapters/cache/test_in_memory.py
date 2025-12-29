import pytest
from unittest.mock import patch
from cascade.adapters.cache.in_memory import InMemoryCacheBackend


@pytest.mark.asyncio
async def test_cache_set_and_get():
    cache = InMemoryCacheBackend()
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"


@pytest.mark.asyncio
async def test_cache_get_non_existent_key():
    cache = InMemoryCacheBackend()
    assert await cache.get("non_existent") is None


@pytest.mark.asyncio
async def test_cache_set_overwrite():
    cache = InMemoryCacheBackend()
    await cache.set("key1", "value1")
    await cache.set("key1", "value2")
    assert await cache.get("key1") == "value2"


@pytest.mark.asyncio
async def test_cache_ttl_not_expired():
    cache = InMemoryCacheBackend()
    with patch("time.time", return_value=1000):
        await cache.set("key_ttl", "value_ttl", ttl=60)

    with patch("time.time", return_value=1059):
        assert await cache.get("key_ttl") == "value_ttl"


@pytest.mark.asyncio
async def test_cache_ttl_expired():
    cache = InMemoryCacheBackend()
    with patch("time.time", return_value=1000):
        await cache.set("key_ttl", "value_ttl", ttl=60)

    # Move time forward to just after the expiry
    with patch("time.time", return_value=1061):
        assert await cache.get("key_ttl") is None

    # Verify that the key was actually removed from the store
    assert "key_ttl" not in cache._store
    assert "key_ttl" not in cache._expiry
