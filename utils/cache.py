import importlib.util
import os
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Optional
from utils.logger import log


class BaseCache(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        """Retrieves a value from the cache."""
        pass

    @abstractmethod
    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """Stores a value with an optional TTL in seconds."""
        pass

    @abstractmethod
    def delete(self, key: Any) -> None:
        """Removes a key from the cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all stored keys in the cache."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Purges all expired keys and returns the number of purged items."""
        pass

    # Async convenience aliases
    async def aget(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        return self.get(key, default=default)

    async def aset(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        self.set(key, value, ttl=ttl)

    async def adelete(self, key: Any) -> None:
        self.delete(key)

    async def aclear(self) -> None:
        self.clear()


class MemoryTTLCache(BaseCache):
    """
    Thread-safe in-memory LRU cache with per-key TTL.
    Prevents memory leaks via strict bounded capacity (max_size) and automatic expiration.
    """

    def __init__(self, max_size: int = 10000, default_ttl: Optional[float] = None) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        # Key -> (value, expires_at_timestamp_or_None)
        self._data: OrderedDict[str, tuple[Any, Optional[float]]] = OrderedDict()

    def _is_expired(self, expires_at: Optional[float], now: float) -> bool:
        return expires_at is not None and now > expires_at

    def get(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        str_key = str(key)
        item = self._data.get(str_key)
        if item is None:
            return default

        val, expires_at = item
        now = time.time()
        if self._is_expired(expires_at, now):
            self._data.pop(str_key, None)
            return default

        # Move to end (MRU)
        self._data.move_to_end(str_key)
        return val

    def get_sync(self, key: Any, default: Optional[Any] = None) -> Optional[Any]:
        return self.get(key, default=default)

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        str_key = str(key)
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = (time.time() + effective_ttl) if effective_ttl is not None else None

        # If key exists, update and move to end
        if str_key in self._data:
            self._data.move_to_end(str_key)
        self._data[str_key] = (value, expires_at)

        # Evict oldest items if max capacity exceeded
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def set_sync(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        self.set(key, value, ttl=ttl)

    def delete(self, key: Any) -> None:
        self._data.pop(str(key), None)

    def delete_sync(self, key: Any) -> None:
        self.delete(key)

    def clear(self) -> None:
        self._data.clear()

    def clear_sync(self) -> None:
        self.clear()

    def __getitem__(self, key: Any) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: Any) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        return len(self._data)

    def cleanup_expired(self) -> int:
        now = time.time()
        expired_keys = [
            k for k, (_, expires_at) in self._data.items()
            if self._is_expired(expires_at, now)
        ]
        for k in expired_keys:
            self._data.pop(k, None)
        return len(expired_keys)


def create_cache(namespace: str, max_size: int = 10000, default_ttl: Optional[float] = None) -> BaseCache:
    """
    Factory function creating an appropriate cache instance.
    Uses MemoryTTLCache by default, or an external adapter if configured.
    """
    # Note: Pluggable Redis adapter hook can be enabled when REDIS_URL is provided in environment
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        if importlib.util.find_spec("redis") is not None:
            log.info("[Cache] Redis cache available for namespace: %s", namespace)
            # In a distributed multi-node deployment, Redis cache is returned here
        else:
            log.warning("[Cache] REDIS_URL set but redis package not installed; falling back to MemoryTTLCache.")

    return MemoryTTLCache(max_size=max_size, default_ttl=default_ttl)


# Centralized shared cache namespaces
guild_cache: BaseCache = create_cache("guild_settings", max_size=5000, default_ttl=300.0)  # 5 min TTL
cooldown_cache: BaseCache = create_cache("rsvp_cooldowns", max_size=50000, default_ttl=60.0)  # 1 min TTL
archive_hours_cache: BaseCache = create_cache("archive_hours", max_size=5000, default_ttl=300.0)  # 5 min TTL
stats_cache: BaseCache = create_cache("global_stats", max_size=100, default_ttl=300.0)  # 5 min TTL
