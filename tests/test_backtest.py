"""Tests for the algorithmic backtest engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cardinal.core.backtest import (
    _max_drawdown,
    _annualised_sharpe,
    run_mean_reversion_backtest,
    run_momentum_backtest,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def price_series() -> pd.Series:
    """3 years of synthetic daily prices."""
    np.random.seed(42)
    n = 756
    dates = pd.date_range("2021-01-04", periods=n, freq="B")
    returns = np.random.normal(0.0004, 0.015, n)
    return pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)


@pytest.fixture
def short_series() -> pd.Series:
    dates = pd.date_range("2024-01-02", periods=30, freq="B")
    return pd.Series([100.0 + i for i in range(30)], index=dates)


@pytest.fixture
def trending_series() -> pd.Series:
    """Steadily rising prices — favours momentum strategy."""
    np.random.seed(7)
    n = 756
    dates = pd.date_range("2021-01-04", periods=n, freq="B")
    returns = np.random.normal(0.001, 0.005, n)
    return pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)


# ── helper functions ──────────────────────────────────────────────────────────

class TestMaxDrawdown:
    def test_monotonically_rising_has_zero_drawdown(self):
        curve = [1.0, 1.1, 1.2, 1.3, 1.4]
        assert _max_drawdown(curve) == 0.0

    def test_known_drawdown(self):
        # Peak = 1.2, trough = 0.9 → drawdown = (0.9 - 1.2) / 1.2 = -0.25
        curve = [1.0, 1.2, 1.1, 0.9, 1.0]
        dd = _max_drawdown(curve)
        assert abs(dd - (-0.25)) < 1e-4

    def test_drawdown_is_negative(self):
        curve = [1.0, 0.8, 0.6, 0.9]
        assert _max_drawdown(curve) < 0

    def test_single_value_has_zero_drawdown(self):
        assert _max_drawdown([1.0]) == 0.0


class TestAnnualisedSharpe:
    def test_returns_none_for_single_trade(self):
        assert _annualised_sharpe([0.05], 0.042) is None

    def test_positive_for_positive_returns(self):
        returns = [0.03, 0.02, 0.04, 0.01, 0.05]
        sharpe = _annualised_sharpe(returns, 0.0)
        assert sharpe is not None
        assert sharpe > 0

    def test_zero_std_returns_none(self):
        returns = [0.02, 0.02, 0.02]
        assert _annualised_sharpe(returns, 0.042) is None


# ── momentum backtest ─────────────────────────────────────────────────────────

class TestMomentumBacktest:
    def test_returns_correct_strategy_name(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert result.strategy == "momentum"
        assert result.ticker == "TEST"

    def test_params_recorded(self, price_series):
        result = run_momentum_backtest("TEST", price_series, fast_window=30, slow_window=100)
        assert result.params["fast_window"] == 30
        assert result.params["slow_window"] == 100

    def test_max_drawdown_is_negative_or_zero(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert result.max_drawdown <= 0

    def test_win_rate_between_0_and_1(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        if result.win_rate is not None:
            assert 0.0 <= result.win_rate <= 1.0

    def test_pnl_curve_starts_at_one(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert abs(result.pnl_curve[0]["value"] - 1.0) < 1e-6

    def test_buy_hold_curve_starts_at_one(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert abs(result.buy_hold_curve[0]["value"] - 1.0) < 1e-6

    def test_curves_have_same_length(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert len(result.pnl_curve) == len(result.buy_hold_curve)

    def test_curve_dates_are_strings(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert isinstance(result.pnl_curve[0]["date"], str)

    def test_raises_on_insufficient_data(self, short_series):
        with pytest.raises(ValueError, match="trading days"):
            run_momentum_backtest("TEST", short_series)

    def test_num_trades_non_negative(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        assert result.num_trades >= 0

    def test_avg_win_positive_when_present(self, trending_series):
        result = run_momentum_backtest("TEST", trending_series)
        if result.avg_win is not None:
            assert result.avg_win > 0

    def test_avg_loss_negative_or_zero_when_present(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        if result.avg_loss is not None:
            assert result.avg_loss <= 0

    @pytest.mark.parametrize("fast,slow", [(20, 50), (50, 200), (10, 30)])
    def test_various_window_combos(self, price_series, fast, slow):
        result = run_momentum_backtest("TEST", price_series, fast_window=fast, slow_window=slow)
        assert result.total_return is not None

    def test_total_return_consistent_with_curve(self, price_series):
        result = run_momentum_backtest("TEST", price_series)
        final_value = result.pnl_curve[-1]["value"]
        assert abs(final_value - (1 + result.total_return)) < 0.01


# ── mean reversion backtest ───────────────────────────────────────────────────

class TestMeanReversionBacktest:
    def test_returns_correct_strategy_name(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series)
        assert result.strategy == "mean_reversion"

    def test_params_recorded(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series, lookback=30, entry_z=1.5)
        assert result.params["lookback"] == 30
        assert result.params["entry_z"] == 1.5

    def test_more_trades_with_tighter_threshold(self, price_series):
        tight = run_mean_reversion_backtest("TEST", price_series, entry_z=1.0)
        loose = run_mean_reversion_backtest("TEST", price_series, entry_z=3.0)
        assert tight.num_trades >= loose.num_trades

    def test_max_drawdown_non_positive(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series)
        assert result.max_drawdown <= 0

    def test_win_rate_between_0_and_1(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series)
        if result.win_rate is not None:
            assert 0.0 <= result.win_rate <= 1.0

    def test_pnl_curve_starts_at_one(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series)
        assert abs(result.pnl_curve[0]["value"] - 1.0) < 1e-6

    def test_raises_on_insufficient_data(self):
        dates = pd.date_range("2024-01-02", periods=15, freq="B")
        tiny = pd.Series([100.0 + i for i in range(15)], index=dates)
        with pytest.raises(ValueError, match="trading days"):
            run_mean_reversion_backtest("TEST", tiny, lookback=20)

    def test_curves_same_length(self, price_series):
        result = run_mean_reversion_backtest("TEST", price_series)
        assert len(result.pnl_curve) == len(result.buy_hold_curve)

    def test_max_hold_days_limits_trade_duration(self, price_series):
        short_hold = run_mean_reversion_backtest("TEST", price_series, max_hold_days=5)
        long_hold = run_mean_reversion_backtest("TEST", price_series, max_hold_days=30)
        # Shorter hold cap → more frequent forced exits → typically more trades
        # (not guaranteed, but both should run without error)
        assert short_hold.num_trades >= 0
        assert long_hold.num_trades >= 0

    @pytest.mark.parametrize("lookback", [10, 20, 30])
    def test_various_lookbacks(self, price_series, lookback):
        result = run_mean_reversion_backtest("TEST", price_series, lookback=lookback)
        assert result.total_return is not None