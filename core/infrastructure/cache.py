"""In-memory cache for connector payloads with configurable expiration."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class CachePolicy:
    ttl_seconds: float = 300.0
    max_entries: int = 1000


@dataclass(frozen=True)
class CacheEntry:
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


@dataclass(frozen=True)
class CacheResult:
    hit: bool
    key: str
    value: Any = None
    age_seconds: float = 0.0


class InMemoryCache:
    """In-memory cache with configurable expiration.
    
    No Redis. No databases. Memory only.
    """

    def __init__(self, default_policy: CachePolicy = None) -> None:
        self._default_policy = default_policy or CachePolicy()
        self._policies: Dict[str, CachePolicy] = {}
        self._store: Dict[str, CacheEntry] = {}
        self._hit_counts: Dict[str, int] = {}

    def set_policy(self, namespace: str, policy: CachePolicy) -> None:
        self._policies[namespace] = policy

    def get_policy(self, namespace: str) -> CachePolicy:
        return self._policies.get(namespace, self._default_policy)

    def get(self, key: str, now: datetime = None) -> CacheResult:
        if now is None:
            now = datetime.now(timezone.utc)

        if key not in self._store:
            return CacheResult(hit=False, key=key)

        entry = self._store[key]
        if now >= entry.expires_at:
            del self._store[key]
            return CacheResult(hit=False, key=key)

        self._hit_counts[key] = self._hit_counts.get(key, 0) + 1
        age = (now - entry.created_at).total_seconds()
        return CacheResult(hit=True, key=key, value=entry.value, age_seconds=age)

    def put(self, key: str, value: Any, namespace: str = "default", now: datetime = None) -> CacheEntry:
        if now is None:
            now = datetime.now(timezone.utc)

        policy = self.get_policy(namespace)
        expires_at = now + timedelta(seconds=policy.ttl_seconds)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=expires_at
        )
        self._store[key] = entry
        self._hit_counts[key] = 0

        if len(self._store) > policy.max_entries:
            self._evict_oldest()

        return entry

    def invalidate(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._hit_counts.pop(key, None)
            return True
        return False

    def invalidate_all(self) -> int:
        count = len(self._store)
        self._store.clear()
        self._hit_counts.clear()
        return count

    def keys(self) -> Tuple[str, ...]:
        return tuple(sorted(self._store.keys()))

    @property
    def size(self) -> int:
        return len(self._store)

    def _evict_oldest(self) -> None:
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
        del self._store[oldest_key]
        self._hit_counts.pop(oldest_key, None)
