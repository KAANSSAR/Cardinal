"""
Market data layer — wraps yfinance to produce a clean FinancialSnapshot.

This is the only module that talks to an external data source for the
fundamental lens. Keeping it isolated means core/dcf.py never needs to
know where its numbers came from, and we can swap in Financial Modeling
Prep later without touching the DCF engine at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from cardinal.core.dcf import FinancialSnapshot
from cardinal.data.utils import safe_get


class TickerNotFoundError(Exception):
    """Raised when yfinance returns no usable data for a ticker."""


class InsufficientDataError(Exception):
    """Raised when a ticker resolves but is missing fields a DCF requires."""


@dataclass(frozen=True)
class CompanyProfile:
    """Light metadata used for display — not required by the DCF engine itself."""

    ticker: str
    name: str
    sector: str | None
    industry: str | None
    currency: str
    exchange: str | None
    market_cap: float | None


def _safe_get(info: dict, *keys: str, default=None):
    """Deprecated alias — kept for backwards compatibility, use safe_get directly."""
    return safe_get(info, *keys, default=default)


def fetch_company_profile(ticker: str) -> CompanyProfile:
    """Fetch lightweight company metadata for display purposes."""
    t = yf.Ticker(ticker)
    info = t.info

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise TickerNotFoundError(f"No market data found for ticker '{ticker}'")

    return CompanyProfile(
        ticker=ticker.upper(),
        name=_safe_get(info, "longName", "shortName", default=ticker.upper()),
        sector=info.get("sector"),
        industry=info.get("industry"),
        currency=info.get("currency", "USD"),
        exchange=info.get("exchange"),
        market_cap=info.get("marketCap"),
    )


def fetch_financial_snapshot(
    ticker: str,
    *,
    risk_free_rate: float = 0.042,
    market_risk_premium: float = 0.055,
) -> FinancialSnapshot:
    """
    Fetch the financial inputs required to run a DCF, normalised into a
    FinancialSnapshot. Raises InsufficientDataError if yfinance is missing
    fields a DCF cannot proceed without (this happens for some ADRs,
    SPACs, and thinly-covered international tickers).
    """
    t = yf.Ticker(ticker)
    info = t.info

    if not info:
        raise TickerNotFoundError(f"No data returned for ticker '{ticker}'")

    current_price = _safe_get(info, "currentPrice", "regularMarketPrice", "previousClose")
    shares_outstanding = info.get("sharesOutstanding")
    free_cash_flow = info.get("freeCashflow")
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    beta = info.get("beta")
    market_cap = info.get("marketCap")

    missing = [
        name for name, value in [
            ("current_price", current_price),
            ("shares_outstanding", shares_outstanding),
            ("free_cash_flow", free_cash_flow),
        ] if value is None
    ]
    if missing:
        raise InsufficientDataError(
            f"Ticker '{ticker}' is missing required fields for DCF: {', '.join(missing)}"
        )

    net_debt = (total_debt or 0.0) - (total_cash or 0.0)

    # Beta is occasionally absent for newly-listed or thinly-traded tickers —
    # default to market beta (1.0) rather than failing the whole valuation.
    resolved_beta = beta if beta is not None else 1.0

    return FinancialSnapshot(
        ticker=ticker.upper(),
        free_cash_flow_ttm=float(free_cash_flow),
        net_debt=float(net_debt),
        shares_outstanding=float(shares_outstanding),
        current_price=float(current_price),
        beta=float(resolved_beta),
        risk_free_rate=risk_free_rate,
        market_risk_premium=market_risk_premium,
        total_debt=float(total_debt) if total_debt is not None else None,
        market_cap=float(market_cap) if market_cap is not None else None,
    )


def fetch_price_history(ticker: str, period: str = "5y", interval: str = "1d"):
    """
    Fetch OHLCV price history as a pandas DataFrame. Used by the quant
    and backtest lenses — kept separate from the DCF snapshot fetch since
    they're needed independently and at different refresh frequencies.
    """
    t = yf.Ticker(ticker)
    history = t.history(period=period, interval=interval)

    if history.empty:
        raise TickerNotFoundError(f"No price history found for ticker '{ticker}'")

    return history
