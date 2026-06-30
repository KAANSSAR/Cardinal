"""
Tests for the market data layer.

yfinance calls are mocked throughout — unit tests should never depend on
live network access or Yahoo Finance's current data. This also makes the
suite deterministic and fast.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from cardinal.data.market_data import (
    InsufficientDataError,
    TickerNotFoundError,
    fetch_company_profile,
    fetch_financial_snapshot,
    fetch_price_history,
)


class FakeTicker:
    """Stand-in for yf.Ticker — exposes the same .info / .history surface."""

    def __init__(self, info: dict | None = None, history: pd.DataFrame | None = None):
        self.info = info if info is not None else {}
        self._history = history if history is not None else pd.DataFrame()

    def history(self, period: str = "5y", interval: str = "1d"):
        return self._history


FULL_INFO = {
    "longName": "Apple Inc.",
    "shortName": "Apple",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "currency": "USD",
    "exchange": "NMS",
    "marketCap": 3.4e12,
    "currentPrice": 227.50,
    "regularMarketPrice": 227.50,
    "sharesOutstanding": 15.4e9,
    "freeCashflow": 99.6e9,
    "totalDebt": 100e9,
    "totalCash": 156.2e9,
    "beta": 1.25,
}


# ── fetch_company_profile ────────────────────────────────────────────────

class TestFetchCompanyProfile:
    def test_parses_full_profile(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=FULL_INFO)
        )
        profile = fetch_company_profile("AAPL")
        assert profile.ticker == "AAPL"
        assert profile.name == "Apple Inc."
        assert profile.sector == "Technology"
        assert profile.market_cap == 3.4e12

    def test_falls_back_to_short_name(self, monkeypatch):
        info = {**FULL_INFO}
        del info["longName"]
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        profile = fetch_company_profile("AAPL")
        assert profile.name == "Apple"

    def test_raises_when_no_price_data(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info={})
        )
        with pytest.raises(TickerNotFoundError):
            fetch_company_profile("FAKETICKER")

    def test_defaults_currency_to_usd(self, monkeypatch):
        info = {**FULL_INFO}
        del info["currency"]
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        profile = fetch_company_profile("AAPL")
        assert profile.currency == "USD"


# ── fetch_financial_snapshot ─────────────────────────────────────────────

class TestFetchFinancialSnapshot:
    def test_parses_full_snapshot(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=FULL_INFO)
        )
        snapshot = fetch_financial_snapshot("AAPL")
        assert snapshot.ticker == "AAPL"
        assert math.isclose(snapshot.free_cash_flow_ttm, 99.6e9)
        assert math.isclose(snapshot.current_price, 227.50)
        assert math.isclose(snapshot.beta, 1.25)

    def test_net_debt_computed_correctly(self, monkeypatch):
        # totalDebt=100e9, totalCash=156.2e9 -> net_debt = -56.2e9
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=FULL_INFO)
        )
        snapshot = fetch_financial_snapshot("AAPL")
        assert math.isclose(snapshot.net_debt, -56.2e9, rel_tol=1e-6)

    def test_missing_beta_defaults_to_one(self, monkeypatch):
        info = {**FULL_INFO}
        del info["beta"]
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        snapshot = fetch_financial_snapshot("AAPL")
        assert snapshot.beta == 1.0

    def test_raises_when_missing_free_cash_flow(self, monkeypatch):
        info = {**FULL_INFO}
        del info["freeCashflow"]
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        with pytest.raises(InsufficientDataError, match="free_cash_flow"):
            fetch_financial_snapshot("AAPL")

    def test_raises_when_missing_shares_outstanding(self, monkeypatch):
        info = {**FULL_INFO}
        del info["sharesOutstanding"]
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        with pytest.raises(InsufficientDataError, match="shares_outstanding"):
            fetch_financial_snapshot("AAPL")

    def test_raises_when_no_data_at_all(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info={})
        )
        with pytest.raises(TickerNotFoundError):
            fetch_financial_snapshot("FAKETICKER")

    def test_custom_risk_free_rate_passed_through(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=FULL_INFO)
        )
        snapshot = fetch_financial_snapshot("AAPL", risk_free_rate=0.05, market_risk_premium=0.06)
        assert snapshot.risk_free_rate == 0.05
        assert snapshot.market_risk_premium == 0.06

    def test_zero_debt_and_cash_gives_zero_net_debt(self, monkeypatch):
        info = {**FULL_INFO, "totalDebt": 0.0, "totalCash": 0.0}
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(info=info)
        )
        snapshot = fetch_financial_snapshot("AAPL")
        assert snapshot.net_debt == 0.0


# ── fetch_price_history ──────────────────────────────────────────────────

class TestFetchPriceHistory:
    def test_returns_dataframe(self, monkeypatch):
        fake_df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1_000_000, 1_200_000],
        })
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker", lambda ticker: FakeTicker(history=fake_df)
        )
        result = fetch_price_history("AAPL")
        assert len(result) == 2
        assert "Close" in result.columns

    def test_raises_on_empty_history(self, monkeypatch):
        monkeypatch.setattr(
            "cardinal.data.market_data.yf.Ticker",
            lambda ticker: FakeTicker(history=pd.DataFrame()),
        )
        with pytest.raises(TickerNotFoundError):
            fetch_price_history("FAKETICKER")
