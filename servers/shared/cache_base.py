"""In-memory TTL cache with max size limit.

Thread-safe for asyncio usage — all methods are synchronous and
designed to be called from within async coroutines without locks.
"""

import time
from collections import OrderedDict
from typing import Any, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """In-memory cache with time-to-live expiry and max size eviction.

    Uses OrderedDict for LRU-like eviction when max_size is reached.
    All operations are O(1) amortized.

    Attributes:
        ttl_seconds: Default TTL for cache entries in seconds.
        max_size: Maximum number of entries before eviction.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 100) -> None:
        """Initialize the cache.

        Args:
            ttl_seconds: Default TTL in seconds. Defaults to 300 (5 minutes).
            max_size: Max entries. Evicts oldest on overflow. Defaults to 100.
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._store: OrderedDict[K, tuple[V, float]] = OrderedDict()

    def get(self, key: K) -> Optional[V]:
        """Retrieve a value from the cache.

        Returns None if the key is not found or the entry has expired.

        Args:
            key: The cache key.

        Returns:
            The cached value, or None.
        """
        if key not in self._store:
            return None

        value, expires_at = self._store[key]
        if time.monotonic() > expires_at:
            del self._store[key]
            return None

        # Move to end for LRU ordering
        self._store.move_to_end(key)
        return value

    def set(self, key: K, value: V, ttl_seconds: Optional[int] = None) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to cache.
            ttl_seconds: Optional per-entry TTL override.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        expires_at = time.monotonic() + ttl

        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expires_at)

        # Evict oldest if over max size
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def delete(self, key: K) -> None:
        """Remove a key from the cache. No-op if key not present."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._store.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        now = time.monotonic()
        expired_keys = [
            k for k, (_, exp) in self._store.items() if now > exp
        ]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)

    def __len__(self) -> int:
        """Return current number of entries (including expired)."""
        return len(self._store)

    def __contains__(self, key: K) -> bool:
        """Check if a non-expired entry exists for the key."""
        return self.get(key) is not None
