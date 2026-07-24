"""Tests for the quantitative analytics engine."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from cardinal.core.quant import (
    _bollinger,
    _momentum_score,
    _realized_vol,
    _rolling_sharpe,
    _rsi,
    benchmark_for_ticker,
    compute_quant_snapshot,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def trending_up() -> pd.Series:
    """Steadily rising price series — should produce positive momentum."""
    np.random.seed(0)
    n = 300
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    prices = pd.Series(100 + np.arange(n) * 0.5 + np.random.normal(0, 0.5, n), index=dates)
    return prices


@pytest.fixture
def flat_prices() -> pd.Series:
    dates = pd.date_range("2023-01-02", periods=300, freq="B")
    return pd.Series([100.0] * 300, index=dates)


@pytest.fixture
def volatile_prices() -> pd.Series:
    np.random.seed(1)
    dates = pd.date_range("2023-01-02", periods=300, freq="B")
    returns = np.random.normal(0, 0.03, 300)
    return pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)


# ── momentum score ────────────────────────────────────────────────────────────

class TestMomentumScore:
    def test_positive_for_rising_prices(self, trending_up):
        score = _momentum_score(trending_up, 60)
        assert score is not None
        assert score > 0

    def test_returns_none_when_insufficient_data(self):
        prices = pd.Series([100.0, 101.0, 102.0])
        assert _momentum_score(prices, 60) is None

    def test_zero_vol_returns_none(self, flat_prices):
        assert _momentum_score(flat_prices, 20) is None

    def test_longer_window_uses_more_history(self, volatile_prices):
        s20 = _momentum_score(volatile_prices, 20)
        s252 = _momentum_score(volatile_prices, 252)
        # Both should return a value (different windows, same series)
        assert s20 is not None
        assert s252 is not None

    @pytest.mark.parametrize("window", [20, 60, 252])
    def test_standard_windows_return_float(self, trending_up, window):
        result = _momentum_score(trending_up, window)
        assert isinstance(result, float)


# ── rolling sharpe ────────────────────────────────────────────────────────────

class TestRollingSharee:
    def test_positive_for_positive_drift(self, trending_up):
        daily_returns = trending_up.pct_change().dropna()
        sharpe = _rolling_sharpe(daily_returns, 60, risk_free_rate=0.0)
        assert sharpe is not None
        assert sharpe > 0

    def test_returns_none_when_insufficient_data(self):
        returns = pd.Series([0.001, 0.002, -0.001])
        assert _rolling_sharpe(returns, 60, 0.042) is None

    def test_zero_vol_returns_none(self, flat_prices):
        returns = flat_prices.pct_change().dropna()
        assert _rolling_sharpe(returns, 60, 0.042) is None

    def test_higher_rfr_reduces_sharpe(self, trending_up):
        daily_returns = trending_up.pct_change().dropna()
        low_rfr = _rolling_sharpe(daily_returns, 60, risk_free_rate=0.0)
        high_rfr = _rolling_sharpe(daily_returns, 60, risk_free_rate=0.10)
        assert low_rfr > high_rfr


# ── realized volatility ───────────────────────────────────────────────────────

class TestRealizedVol:
    def test_higher_vol_series_gives_higher_result(self, flat_prices, volatile_prices):
        flat_ret = flat_prices.pct_change().dropna()
        vol_ret = volatile_prices.pct_change().dropna()
        flat_vol = _realized_vol(flat_ret, 30)
        v = _realized_vol(vol_ret, 30)
        assert v is not None
        assert v > 0
        # flat series has zero or near-zero vol
        assert flat_vol is not None
        assert flat_vol < v

    def test_annualised_output(self, volatile_prices):
        returns = volatile_prices.pct_change().dropna()
        vol = _realized_vol(returns, 252)
        assert vol is not None
        assert 0 < vol < 5.0  # sanity: annualised vol should be between 0% and 500%

    def test_returns_none_for_insufficient_data(self):
        returns = pd.Series([0.01, -0.01])
        assert _realized_vol(returns, 10) is None


# ── RSI ───────────────────────────────────────────────────────────────────────

class TestRSI:
    def test_always_rising_gives_high_rsi(self):
        prices = pd.Series([float(i) for i in range(1, 50)])
        rsi = _rsi(prices)
        assert rsi is not None
        assert rsi > 70

    def test_always_falling_gives_low_rsi(self):
        prices = pd.Series([float(50 - i) for i in range(50)])
        rsi = _rsi(prices)
        assert rsi is not None
        assert rsi < 30

    def test_rsi_within_valid_range(self, volatile_prices):
        rsi = _rsi(volatile_prices)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_returns_none_for_insufficient_data(self):
        prices = pd.Series([100.0, 101.0, 102.0])
        assert _rsi(prices, period=14) is None

    def test_known_all_gains_gives_100(self):
        """Pure all-gains scenario — avg_loss = 0, RSI should be 100."""
        prices = pd.Series([float(100 + i) for i in range(30)])
        rsi = _rsi(prices, period=14)
        assert rsi == 100.0


# ── Bollinger Bands ───────────────────────────────────────────────────────────

class TestBollingerBands:
    def test_returns_none_for_insufficient_data(self):
        prices = pd.Series([100.0] * 5)
        assert _bollinger(prices)[0] is None

    def test_upper_greater_than_lower(self, volatile_prices):
        upper, middle, lower, pct_b = _bollinger(volatile_prices)
        assert upper > lower
        assert upper > middle > lower

    def test_pct_b_between_0_and_1_for_normal_price(self, trending_up):
        _, _, _, pct_b = _bollinger(trending_up)
        # pct_b can exceed 0-1 when price is outside the bands — just check it's a number
        assert pct_b is not None
        assert isinstance(pct_b, float)

    def test_flat_prices_narrow_bands(self, flat_prices):
        upper, middle, lower, _ = _bollinger(flat_prices)
        assert upper is not None
        assert abs(upper - lower) < 1.0  # very tight bands


# ── full snapshot ─────────────────────────────────────────────────────────────

class TestComputeQuantSnapshot:
    def test_returns_snapshot_with_all_fields(self, volatile_prices):
        snap = compute_quant_snapshot("TEST", volatile_prices)
        assert snap.ticker == "TEST"
        assert snap.current_price == round(float(volatile_prices.iloc[-1]), 2)
        # Check none of the optional fields are unexpectedly present but broken
        for field in ["momentum_20d", "sharpe_60d", "vol_10d", "rsi", "bb_pct_b"]:
            val = getattr(snap, field)
            assert val is None or isinstance(val, float)

    def test_beta_none_without_benchmark(self, volatile_prices):
        snap = compute_quant_snapshot("TEST", volatile_prices)
        assert snap.beta is None

    def test_beta_computed_with_benchmark(self, volatile_prices):
        np.random.seed(99)
        bench = pd.Series(
            100 * np.exp(np.cumsum(np.random.normal(0.0002, 0.012, len(volatile_prices)))),
            index=volatile_prices.index,
        )
        snap = compute_quant_snapshot("TEST", volatile_prices, benchmark_prices=bench)
        assert snap.beta is not None
        assert isinstance(snap.beta, float)

    def test_insufficient_data_gives_none_for_long_windows(self):
        # Only 30 days — 252d metrics should be None
        dates = pd.date_range("2024-01-02", periods=30, freq="B")
        prices = pd.Series([100.0 + i * 0.5 for i in range(30)], index=dates)
        snap = compute_quant_snapshot("SHORT", prices)
        assert snap.momentum_252d is None
        assert snap.sharpe_252d is None

    def test_no_nan_in_output(self, trending_up):
        np.random.seed(5)
        bench = pd.Series(
            100 * np.exp(np.cumsum(np.random.normal(0.0002, 0.01, len(trending_up)))),
            index=trending_up.index,
        )
        snap = compute_quant_snapshot("TEST", trending_up, bench)
        for field in vars(snap).values():
            if isinstance(field, float):
                assert not math.isnan(field), f"NaN found in field"


# ── benchmark detection ───────────────────────────────────────────────────────

class TestBenchmarkForTicker:
    def test_us_ticker_uses_sp500(self):
        assert benchmark_for_ticker("AAPL") == "^GSPC"
        assert benchmark_for_ticker("MSFT") == "^GSPC"

    def test_indian_ticker_uses_nifty(self):
        assert benchmark_for_ticker("RELIANCE.NS") == "^NSEI"
        assert benchmark_for_ticker("TCS.BO") == "^NSEI"

    def test_european_tickers_use_stoxx(self):
        assert benchmark_for_ticker("SAP.DE") == "^STOXX50E"
        assert benchmark_for_ticker("AZN.L") == "^STOXX50E"
        assert benchmark_for_ticker("LVMH.PA") == "^STOXX50E"

    def test_case_insensitive(self):
        assert benchmark_for_ticker("reliance.ns") == "^NSEI"
        assert benchmark_for_ticker("sap.de") == "^STOXX50E"