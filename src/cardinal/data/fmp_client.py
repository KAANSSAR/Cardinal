"""
Financial Modeling Prep (FMP) client — primary fundamental data source for
US tickers, per Cardinal's architecture (yfinance remains the source for
price history and EU/India fallback financials).

Uses FMP's current 'stable' endpoint scheme:
https://financialmodelingprep.com/stable/{resource}?symbol={ticker}&apikey={key}

All HTTP calls are isolated in this module — core/dcf.py never knows
where its numbers came from, identical separation to market_data.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from cardinal.config import settings
from cardinal.core.dcf import FinancialSnapshot
from cardinal.data.utils import safe_get


class FMPNotConfiguredError(Exception):
    """Raised when no FMP API key is set in the environment."""


class FMPRequestError(Exception):
    """Raised when FMP returns a non-200 response or a malformed payload."""


class TickerNotFoundError(Exception):
    """Raised when FMP returns no usable data for a ticker."""


class InsufficientDataError(Exception):
    """Raised when a ticker resolves but is missing fields a DCF requires."""


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    sector: str | None
    industry: str | None
    currency: str
    exchange: str | None
    market_cap: float | None
    beta: float | None


def _require_api_key() -> str:
    if not settings.fmp_configured:
        raise FMPNotConfiguredError(
            "FMP_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return settings.fmp_api_key  # type: ignore[return-value]


def _get(resource: str, symbol: str, **params) -> list[dict] | dict:
    """Shared GET wrapper — every FMP stable endpoint follows the same shape."""
    api_key = _require_api_key()
    url = f"{settings.fmp_base_url}/{resource}"
    query = {"symbol": symbol, "apikey": api_key, **params}

    try:
        response = httpx.get(url, params=query, timeout=10.0)
    except httpx.RequestError as e:
        raise FMPRequestError(f"Network error calling FMP ({resource}): {e}") from e

    if response.status_code != 200:
        raise FMPRequestError(
            f"FMP returned status {response.status_code} for {resource}/{symbol}"
        )

    data = response.json()
    if isinstance(data, dict) and "Error Message" in data:
        raise TickerNotFoundError(f"FMP error for '{symbol}': {data['Error Message']}")

    return data


def get_profile(ticker: str) -> dict:
    data = _get("profile", ticker)
    if not data:
        raise TickerNotFoundError(f"No FMP profile found for ticker '{ticker}'")
    return data[0] if isinstance(data, list) else data


def get_quote(ticker: str) -> dict:
    data = _get("quote", ticker)
    if not data:
        raise TickerNotFoundError(f"No FMP quote found for ticker '{ticker}'")
    return data[0] if isinstance(data, list) else data


def get_income_statement(ticker: str, *, period: str = "annual", limit: int = 3) -> list[dict]:
    data = _get("income-statement", ticker, period=period, limit=limit)
    if not data:
        raise TickerNotFoundError(f"No FMP income statement found for ticker '{ticker}'")
    return data  # type: ignore[return-value]


def get_balance_sheet_statement(ticker: str, *, period: str = "annual", limit: int = 3) -> list[dict]:
    data = _get("balance-sheet-statement", ticker, period=period, limit=limit)
    if not data:
        raise TickerNotFoundError(f"No FMP balance sheet found for ticker '{ticker}'")
    return data  # type: ignore[return-value]


def get_cash_flow_statement(ticker: str, *, period: str = "annual", limit: int = 3) -> list[dict]:
    data = _get("cash-flow-statement", ticker, period=period, limit=limit)
    if not data:
        raise TickerNotFoundError(f"No FMP cash flow statement found for ticker '{ticker}'")
    return data  # type: ignore[return-value]


def get_stock_peers(ticker: str) -> list[str]:
    """
    Returns a list of peer ticker symbols for the given company.
    FMP's stable/stock-peers endpoint returns a flat list of peer objects,
    each with symbol, companyName, price, mktCap.
    """
    api_key = _require_api_key()
    url = f"{settings.fmp_base_url}/stock-peers"
    try:
        response = httpx.get(url, params={"symbol": ticker, "apikey": api_key}, timeout=10.0)
    except httpx.RequestError as e:
        raise FMPRequestError(f"Network error fetching peers for '{ticker}': {e}") from e

    if response.status_code != 200:
        raise FMPRequestError(f"FMP returned status {response.status_code} for stock-peers/{ticker}")

    data = response.json()
    if not data or not isinstance(data, list):
        return []

    # Each item is {"symbol": "MSFT", "companyName": "...", "price": ..., "mktCap": ...}
    return [item["symbol"] for item in data if isinstance(item, dict) and "symbol" in item]


def get_key_metrics_ttm(ticker: str) -> dict:
    """
    TTM key metrics — includes EV/EBITDA, P/E, P/S, EV/Revenue, market cap.
    Used for the comparable companies table.
    """
    data = _get("key-metrics-ttm", ticker)
    if not data:
        raise TickerNotFoundError(f"No FMP TTM key metrics found for ticker '{ticker}'")
    return data[0] if isinstance(data, list) else data


def fetch_company_profile(ticker: str) -> CompanyProfile:
    """FMP equivalent of market_data.fetch_company_profile — same return shape philosophy."""
    profile = get_profile(ticker)

    return CompanyProfile(
        ticker=ticker.upper(),
        name=safe_get(profile, "companyName", default=ticker.upper()),
        sector=profile.get("sector"),
        industry=profile.get("industry"),
        currency=profile.get("currency", "USD"),
        exchange=profile.get("exchangeShortName"),
        market_cap=profile.get("marketCap"),
        beta=profile.get("beta"),
    )


def fetch_financial_snapshot(
    ticker: str,
    *,
    risk_free_rate: float = 0.042,
    market_risk_premium: float = 0.055,
) -> FinancialSnapshot:
    """
    Build a FinancialSnapshot from FMP's profile + cash flow + balance
    sheet endpoints. Same output contract as market_data.fetch_financial_snapshot,
    so core/dcf.py is completely agnostic to which one fed it.
    """
    profile = get_profile(ticker)
    cash_flow = get_cash_flow_statement(ticker, limit=1)
    balance_sheet = get_balance_sheet_statement(ticker, limit=1)

    current_price = profile.get("price")
    shares_outstanding = (
        safe_get(profile, "sharesOutstanding")
        or safe_get(balance_sheet[0] if balance_sheet else {}, "commonStockSharesOutstanding")
    )
    free_cash_flow = cash_flow[0].get("freeCashFlow") if cash_flow else None
    total_debt = balance_sheet[0].get("totalDebt") if balance_sheet else None
    cash_and_equivalents = balance_sheet[0].get("cashAndCashEquivalents") if balance_sheet else None
    beta = profile.get("beta")
    market_cap = profile.get("marketCap")

    missing = [
        name for name, value in [
            ("current_price", current_price),
            ("shares_outstanding", shares_outstanding),
            ("free_cash_flow", free_cash_flow),
        ] if value is None
    ]
    if missing:
        raise InsufficientDataError(
            f"Ticker '{ticker}' is missing required FMP fields for DCF: {', '.join(missing)}"
        )

    net_debt = (total_debt or 0.0) - (cash_and_equivalents or 0.0)
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