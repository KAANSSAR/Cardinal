"""
Simple in-memory agent memo cache.

Keyed by a hash of the agent name + ticker + relevant parameters.
TTL defaults to 1 hour — financial data doesn't change intraday enough
to warrant more frequent re-runs.

Production upgrade path: swap _store for Redis with the same interface.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

CACHE_TTL = timedelta(hours=1)
_store: dict[str, tuple[str, datetime]] = {}


def make_key(*parts: object) -> str:
    """Hash any combination of values into a cache key."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def get(key: str) -> str | None:
    """Return the cached memo, or None if absent or expired."""
    if key not in _store:
        return None
    memo, ts = _store[key]
    if datetime.now(timezone.utc) - ts > CACHE_TTL:
        del _store[key]
        return None
    return memo


def set(key: str, memo: str) -> None:
    """Store a memo in the cache with the current timestamp."""
    _store[key] = (memo, datetime.now(timezone.utc))


def clear() -> None:
    """Wipe the entire cache — useful for testing."""
    _store.clear()


def size() -> int:
    """Number of currently cached entries."""
    return len(_store)