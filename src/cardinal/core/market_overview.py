"""
Market overview — homepage widgets: indices, gainers/losers, sector heatmap.

All data sourced from yfinance (no premium FMP endpoints needed — sector
performance uses SPDR sector ETFs as proxies, which is standard practice
even on paid terminals when a dedicated sector-performance feed isn't available).

Short-TTL cache (60s) keeps repeat homepage loads fast without hammering
yfinance on every request. Separate from agents/cache.py (which uses a
1-hour TTL suited to LLM memos, not live-ish market data).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import yfinance as yf

# ── Short-TTL cache (60s) — separate from the agent memo cache ────────────────

_CACHE_TTL_SECONDS = 60
_cache: dict[str, tuple[object, float]] = {}


def _cache_get(key: str):
    if key not in _cache:
        return None
    value, ts = _cache[key]
    if time.time() - ts > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (value, time.time())


# ── Universe definitions ────────────────────────────────────────────────────

INDEX_TICKERS: dict[str, str] = {
    "^GSPC": "S&P 500",
    "^NSEI": "NIFTY 50",
    "^GDAXI": "DAX",
}

# Large-cap universe for gainers/losers ranking — spans tech, finance, retail,
# industrials, and healthcare so the movers list isn't tech-only.
MOVERS_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "AMD",
    "NFLX", "JPM", "V", "WMT", "DIS", "BA", "INTC", "PLTR", "COIN", "PYPL", "CRM",
]

# GICS sector proxies via SPDR sector ETFs — 10 sectors (Consumer Staples
# omitted to match a clean 5x2 heatmap grid).
SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLC": "Comm. Services",
    "XLY": "Consumer Disc.",
    "XLF": "Financials",
    "XLU": "Utilities",
    "XLI": "Industrials",
    "XLV": "Healthcare",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLE": "Energy",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SparklinePoint:
    date: str
    value: float


@dataclass(frozen=True)
class IndexQuote:
    symbol: str
    name: str
    value: float
    change: float
    change_pct: float
    sparkline: list[SparklinePoint]


@dataclass(frozen=True)
class MoverQuote:
    ticker: str
    name: str
    price: float
    change_pct: float
    sparkline: list[SparklinePoint]


@dataclass(frozen=True)
class SectorPerformance:
    name: str
    etf_proxy: str
    change_pct: float


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_history_with_sparkline(symbol: str):
    """
    Fetch 1mo daily history for a ticker. Returns (history_df, sparkline_points)
    or (None, []) if unavailable. ~21 trading days gives a smooth sparkline
    without needing intraday data (which is flaky outside market hours).
    """
    try:
        hist = yf.Ticker(symbol).history(period="1mo", interval="1d")
        if hist.empty or len(hist) < 2:
            return None, []
        sparkline = [
            SparklinePoint(date=str(idx.date()), value=round(float(row["Close"]), 4))
            for idx, row in hist.iterrows()
        ]
        return hist, sparkline
    except Exception:
        return None, []


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_market_indices() -> list[IndexQuote]:
    """Fetch S&P 500, NIFTY 50, DAX — current value, change, sparkline."""
    cached = _cache_get("indices")
    if cached is not None:
        return cached

    results: list[IndexQuote] = []
    for symbol, name in INDEX_TICKERS.items():
        hist, sparkline = _fetch_history_with_sparkline(symbol)
        if hist is None:
            continue
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change = last_close - prev_close
        change_pct = change / prev_close if prev_close else 0.0
        results.append(IndexQuote(
            symbol=symbol, name=name, value=round(last_close, 2),
            change=round(change, 2), change_pct=round(change_pct, 4),
            sparkline=sparkline,
        ))

    _cache_set("indices", results)
    return results


def fetch_market_movers(limit: int = 5) -> tuple[list[MoverQuote], list[MoverQuote]]:
    """
    Fetch day-over-day % change for the movers universe, rank into
    top N gainers and top N losers.
    """
    cache_key = f"movers_{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    quotes: list[MoverQuote] = []
    for ticker in MOVERS_UNIVERSE:
        hist, sparkline = _fetch_history_with_sparkline(ticker)
        if hist is None:
            continue
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = (last_close - prev_close) / prev_close if prev_close else 0.0

        name = ticker
        try:
            info = yf.Ticker(ticker).info
            name = info.get("shortName") or info.get("longName") or ticker
        except Exception:
            pass

        quotes.append(MoverQuote(
            ticker=ticker, name=name, price=round(last_close, 2),
            change_pct=round(change_pct, 4), sparkline=sparkline,
        ))

    ranked = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
    gainers = ranked[:limit]
    losers = list(reversed(ranked[-limit:])) if len(ranked) >= limit else []

    result = (gainers, losers)
    _cache_set(cache_key, result)
    return result


def fetch_sector_heatmap() -> list[SectorPerformance]:
    """Fetch day-over-day % change for the 10 GICS sector ETF proxies."""
    cached = _cache_get("sectors")
    if cached is not None:
        return cached

    results: list[SectorPerformance] = []
    for etf, name in SECTOR_ETFS.items():
        hist, _ = _fetch_history_with_sparkline(etf)
        if hist is None:
            continue
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = (last_close - prev_close) / prev_close if prev_close else 0.0
        results.append(SectorPerformance(
            name=name, etf_proxy=etf, change_pct=round(change_pct, 4),
        ))

    _cache_set("sectors", results)
    return results


def clear_cache() -> None:
    """Wipe the market data cache — useful for testing."""
    _cache.clear()


@dataclass(frozen=True)
class TapeQuote:
    ticker: str
    name: str
    price: float
    change_pct: float


def fetch_ticker_tape() -> list[TapeQuote]:
    """
    Fetch a fixed-order watchlist for the header marquee — unlike movers,
    this is NOT re-ranked by performance, so tape items stay in a stable
    order across refreshes (matches real terminal tape behaviour).
    """
    cached = _cache_get("ticker_tape")
    if cached is not None:
        return cached

    results: list[TapeQuote] = []
    for ticker in MOVERS_UNIVERSE:
        hist, _ = _fetch_history_with_sparkline(ticker)
        if hist is None:
            continue
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = (last_close - prev_close) / prev_close if prev_close else 0.0
        results.append(TapeQuote(
            ticker=ticker, name=ticker, price=round(last_close, 2),
            change_pct=round(change_pct, 4),
        ))

    _cache_set("ticker_tape", results)
    return results