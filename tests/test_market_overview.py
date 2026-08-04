"""Tests for the market overview module (homepage widgets)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cardinal.api.main import app
from cardinal.core import market_overview as mo

client = TestClient(app)


def _fake_history(start_price: float = 100.0, days: int = 21, drift: float = 0.01):
    """Build a fake yfinance-style history DataFrame with a gentle uptrend."""
    dates = pd.date_range("2026-07-01", periods=days, freq="B")
    prices = [start_price * (1 + drift) ** i for i in range(days)]
    return pd.DataFrame({
        "Open": prices, "High": [p * 1.01 for p in prices],
        "Low": [p * 0.99 for p in prices], "Close": prices,
        "Volume": [1_000_000] * days,
    }, index=dates)


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure the short-TTL cache doesn't leak state between tests."""
    mo.clear_cache()
    yield
    mo.clear_cache()


class TestFetchMarketIndices:
    def test_returns_all_configured_indices(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_market_indices()
        assert len(results) == len(mo.INDEX_TICKERS)

    def test_computes_change_correctly(self):
        fake_hist = _fake_history(start_price=100.0, days=5, drift=0.0)
        # Force last close higher than prev close
        fake_hist.iloc[-1, fake_hist.columns.get_loc("Close")] = 110.0
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_market_indices()
        assert all(r.change_pct > 0 for r in results)

    def test_skips_index_on_empty_history(self):
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            results = mo.fetch_market_indices()
        assert results == []

    def test_sparkline_has_multiple_points(self):
        fake_hist = _fake_history(days=21)
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_market_indices()
        assert len(results[0].sparkline) == 21

    def test_uses_cache_on_second_call(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            mo.fetch_market_indices()
            call_count_after_first = mock_ticker.call_count
            mo.fetch_market_indices()
            call_count_after_second = mock_ticker.call_count
        assert call_count_after_second == call_count_after_first  # no new calls


class TestFetchMarketMovers:
    def test_returns_gainers_and_losers(self):
        fake_hist = _fake_history()
        fake_info = {"shortName": "Test Co"}
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.return_value = fake_hist
            instance.info = fake_info
            mock_ticker.return_value = instance
            gainers, losers = mo.fetch_market_movers(limit=5)
        assert len(gainers) <= 5
        assert len(losers) <= 5

    def test_gainers_sorted_descending(self):
        """Gainers should be sorted with the biggest % gain first."""
        def variable_history(*args, **kwargs):
            return _fake_history(drift=0.02)

        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.side_effect = variable_history
            instance.info = {"shortName": "Test"}
            mock_ticker.return_value = instance
            gainers, _ = mo.fetch_market_movers(limit=3)
        pcts = [g.change_pct for g in gainers]
        assert pcts == sorted(pcts, reverse=True)

    def test_handles_missing_info_gracefully(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.return_value = fake_hist
            instance.info = MagicMock(side_effect=Exception("no info"))
            type(instance).info = property(lambda self: (_ for _ in ()).throw(Exception("fail")))
            mock_ticker.return_value = instance
            gainers, losers = mo.fetch_market_movers(limit=5)
        # Should not raise — falls back to ticker symbol as name
        assert isinstance(gainers, list)


class TestFetchSectorHeatmap:
    def test_returns_ten_sectors(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_sector_heatmap()
        assert len(results) == len(mo.SECTOR_ETFS)

    def test_sector_names_match_config(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_sector_heatmap()
        names = {s.name for s in results}
        assert names == set(mo.SECTOR_ETFS.values())


class TestFetchTickerTape:
    def test_returns_full_universe(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_ticker_tape()
        assert len(results) == len(mo.MOVERS_UNIVERSE)

    def test_stable_order_not_reranked(self):
        """Tape order should match MOVERS_UNIVERSE order, not be sorted by performance."""
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            results = mo.fetch_ticker_tape()
        tickers_in_order = [r.ticker for r in results]
        assert tickers_in_order == mo.MOVERS_UNIVERSE

    def test_uses_cache_on_second_call(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            mo.fetch_ticker_tape()
            count_after_first = mock_ticker.call_count
            mo.fetch_ticker_tape()
            count_after_second = mock_ticker.call_count
        assert count_after_second == count_after_first


class TestMarketEndpoints:
    def test_indices_endpoint_returns_200(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            response = client.get("/market/indices")
        assert response.status_code == 200
        body = response.json()
        assert "indices" in body

    def test_movers_endpoint_returns_200(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.return_value = fake_hist
            instance.info = {"shortName": "Test Co"}
            mock_ticker.return_value = instance
            response = client.get("/market/movers")
        assert response.status_code == 200
        body = response.json()
        assert "gainers" in body
        assert "losers" in body

    def test_movers_endpoint_respects_limit_param(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            instance = MagicMock()
            instance.history.return_value = fake_hist
            instance.info = {"shortName": "Test Co"}
            mock_ticker.return_value = instance
            response = client.get("/market/movers", params={"limit": 3})
        body = response.json()
        assert len(body["gainers"]) <= 3

    def test_sectors_endpoint_returns_200(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            response = client.get("/market/sectors")
        assert response.status_code == 200
        body = response.json()
        assert len(body["sectors"]) == 10

    def test_ticker_tape_endpoint_returns_200(self):
        fake_hist = _fake_history()
        with patch("cardinal.core.market_overview.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            response = client.get("/market/ticker-tape")
        assert response.status_code == 200
        body = response.json()
        assert len(body["quotes"]) == len(mo.MOVERS_UNIVERSE)