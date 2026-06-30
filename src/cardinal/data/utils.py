"""Small shared helpers used by both the yfinance and FMP data sources."""

from __future__ import annotations


def safe_get(data: dict, *keys: str, default=None):
    """Return the first present, non-None value among the given keys."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default
