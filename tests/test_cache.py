import time
from unittest.mock import AsyncMock, patch

import pytest

from utils.cache import MemoryTTLCache
from utils.i18n import invalidate_guild_cache, load_guild_translations


@pytest.mark.asyncio
async def test_memory_ttl_cache_basic():
    cache = MemoryTTLCache(max_size=10, default_ttl=60.0)
    assert len(cache) == 0

    # Test sync set and get
    cache.set("k1", "val1")
    assert cache.get("k1") == "val1"
    assert cache.get_sync("k1") == "val1"
    assert "k1" in cache
    assert len(cache) == 1

    # Test async alias
    await cache.aset("k2", "val2")
    assert await cache.aget("k2") == "val2"
    assert len(cache) == 2

    # Test delete
    cache.delete("k1")
    assert cache.get("k1") is None
    assert "k1" not in cache
    assert len(cache) == 1

    await cache.adelete("k2")
    assert len(cache) == 0


@pytest.mark.asyncio
async def test_memory_ttl_cache_expiration():
    cache = MemoryTTLCache(max_size=10, default_ttl=0.1)  # 100ms TTL

    cache.set("quick", "expires_soon")
    assert cache.get("quick") == "expires_soon"

    # Sleep past expiration
    time.sleep(0.15)
    assert cache.get("quick") is None
    assert cache.get_sync("quick") is None
    assert "quick" not in cache


def test_memory_ttl_cache_cleanup_expired():
    cache = MemoryTTLCache(max_size=10)
    cache.set_sync("active", "stays", ttl=60.0)
    cache.set_sync("expired1", "gone", ttl=0.01)
    cache.set_sync("expired2", "gone", ttl=0.01)

    time.sleep(0.05)
    purged = cache.cleanup_expired()
    assert purged == 2
    assert len(cache) == 1
    assert cache.get_sync("active") == "stays"


def test_memory_ttl_cache_capacity_eviction():
    cache = MemoryTTLCache(max_size=3)
    cache.set_sync("a", 1)
    cache.set_sync("b", 2)
    cache.set_sync("c", 3)
    assert len(cache) == 3

    # Access "a" so "b" becomes the oldest accessed (LRU)
    assert cache.get_sync("a") == 1

    # Add 4th item, should evict "b"
    cache.set_sync("d", 4)
    assert len(cache) == 3
    assert cache.get_sync("b") is None
    assert cache.get_sync("a") == 1
    assert cache.get_sync("c") == 3
    assert cache.get_sync("d") == 4


def test_memory_ttl_cache_dict_compatibility():
    cache = MemoryTTLCache(max_size=10, default_ttl=60.0)
    cache["k1"] = "v1"
    assert cache["k1"] == "v1"
    assert cache.get_sync("k1") == "v1"
    assert cache.get_sync("nonexistent", default=42) == 42

    with pytest.raises(KeyError):
        _ = cache["missing"]

    cache.clear_sync()
    assert len(cache) == 0


@pytest.mark.asyncio
async def test_guild_cache_and_invalidation():
    guild_id = "987654321"
    invalidate_guild_cache(guild_id)

    mock_trans = {"LBL_TEST": "Custom Label"}
    mock_settings = {"language": "hu", "timezone": "Europe/Budapest"}

    with patch("database.get_guild_translations", new_callable=AsyncMock, return_value=mock_trans) as mock_get_t, \
         patch("database.get_all_guild_settings", new_callable=AsyncMock, return_value=mock_settings) as mock_get_s:

        # 1. First fetch loads from DB
        data1 = await load_guild_translations(guild_id)
        assert data1["lang"] == "hu"
        assert data1["overrides"]["LBL_TEST"] == "Custom Label"
        assert mock_get_t.call_count == 1
        assert mock_get_s.call_count == 1

        # 2. Second fetch uses guild_cache (0 new DB calls!)
        data2 = await load_guild_translations(guild_id)
        assert data2 == data1
        assert mock_get_t.call_count == 1
        assert mock_get_s.call_count == 1

        # 3. Invalidate cache
        invalidate_guild_cache(guild_id)

        # 4. Third fetch hits DB again because cache was invalidated
        data3 = await load_guild_translations(guild_id)
        assert data3 == data1
        assert mock_get_t.call_count == 2
        assert mock_get_s.call_count == 2
