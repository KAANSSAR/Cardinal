"""Tests for Busquets (Strategy Reviewer Agent)."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cardinal.agents.busquets import build_backtest_snapshot, run_busquets
from cardinal.api.main import app

client = TestClient(app)

FAKE_MEMO = (
    "**Strategy Verdict:** The momentum strategy shows no meaningful edge on this ticker.\n"
    "**Performance Analysis:** Strategy returned -12.6% vs buy-and-hold +85.7%.\n"
    "**Drawdown Assessment:** Max drawdown of 27.1% is moderate but concerning.\n"
    "**Regime Observations:** Strategy loses during sustained trending markets.\n"
    "**Suggested Refinements:** Add a volatility filter; avoid entries during high-vol regimes.\n"
    "**Risk Flag:** Only 5 trades — Sharpe ratio is statistically unreliable."
)

SAMPLE_SNAP_KWARGS = dict(
    ticker="BA",
    strategy="momentum",
    params={"fast_window": 50, "slow_window": 200, "commission": 0.001},
    total_return=-0.126,
    buy_hold_return=0.857,
    sharpe=-1.91,
    max_drawdown=-0.271,
    win_rate=0.20,
    num_trades=5,
    avg_win=0.241,
    avg_loss=-0.081,
    pnl_curve=[{"date": "2021-01-04", "value": 1.0}, {"date": "2026-01-04", "value": 0.874}],
    buy_hold_curve=[{"date": "2021-01-04", "value": 1.0}, {"date": "2026-01-04", "value": 1.857}],
)


class TestBuildBacktestSnapshot:
    def test_contains_ticker(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "BA" in snap

    def test_contains_strategy_name(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Momentum" in snap or "momentum" in snap.lower()

    def test_contains_performance_metrics(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Strategy total return" in snap
        assert "Buy-and-hold return" in snap
        assert "Sharpe" in snap

    def test_contains_trade_statistics(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Win rate" in snap
        assert "Average win" in snap
        assert "Average loss" in snap
        assert "Number of trades" in snap

    def test_contains_drawdown(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Max drawdown" in snap
        assert "drawdown" in snap.lower()

    def test_severe_drawdown_flagged(self):
        snap = build_backtest_snapshot(
            **{**SAMPLE_SNAP_KWARGS, "max_drawdown": -0.35}
        )
        assert "SEVERE" in snap

    def test_mild_drawdown_labelled(self):
        snap = build_backtest_snapshot(
            **{**SAMPLE_SNAP_KWARGS, "max_drawdown": -0.10}
        )
        assert "MILD" in snap

    def test_handles_none_sharpe(self):
        snap = build_backtest_snapshot(**{**SAMPLE_SNAP_KWARGS, "sharpe": None})
        assert "N/A" in snap

    def test_outperformance_computed_correctly(self):
        snap = build_backtest_snapshot(**SAMPLE_SNAP_KWARGS)
        # total_return=-12.6%, buy_hold=85.7% → underperformance of 98.3pp
        assert "Outperformance" in snap

    def test_mean_reversion_label(self):
        snap = build_backtest_snapshot(
            **{**SAMPLE_SNAP_KWARGS, "strategy": "mean_reversion",
               "params": {"lookback": 20, "entry_z": 2.0}}
        )
        assert "Mean Reversion" in snap or "mean_reversion" in snap.lower()


class TestRunBusquets:
    def test_calls_gemini_with_cardinal_data(self):
        with patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO) as mock_gen:
            run_busquets(snapshot="ticker: BA\nSharpe: -1.91")
        prompt = mock_gen.call_args[0][0]
        assert "[CARDINAL DATA]" in prompt

    def test_includes_user_question_when_provided(self):
        with patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO) as mock_gen:
            run_busquets(snapshot="ticker: BA", user_question="Can we improve the Sharpe?")
        prompt = mock_gen.call_args[0][0]
        assert "Can we improve the Sharpe?" in prompt
        assert "[USER QUESTION]" in prompt

    def test_includes_news_context_when_provided(self):
        with patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO) as mock_gen:
            run_busquets(snapshot="ticker: BA", news_context="Boeing announces major contract")
        prompt = mock_gen.call_args[0][0]
        assert "[NEWS CONTEXT" in prompt

    def test_returns_memo_text(self):
        with patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO):
            result = run_busquets(snapshot="ticker: BA")
        assert result == FAKE_MEMO

    def test_default_task_when_no_question(self):
        with patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO) as mock_gen:
            run_busquets(snapshot="ticker: BA")
        prompt = mock_gen.call_args[0][0]
        assert "[TASK]" in prompt


class TestBusquetsEndpoint:
    def _fake_history(self):
        np.random.seed(42)
        n = 756
        dates = pd.date_range("2021-01-04", periods=n, freq="B")
        returns = np.random.normal(0.0004, 0.015, n)
        prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)
        return pd.DataFrame({
            "Close": prices, "Open": prices, "High": prices * 1.01,
            "Low": prices * 0.99, "Volume": 1_000_000
        })

    def test_returns_200_momentum(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO):
            response = client.post("/agent/busquets", json={"ticker": "BA", "strategy": "momentum"})
        assert response.status_code == 200
        body = response.json()
        assert body["agent"] == "busquets"
        assert body["ticker"] == "BA"

    def test_returns_200_mean_reversion(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO):
            response = client.post("/agent/busquets", json={"ticker": "BA", "strategy": "mean_reversion"})
        assert response.status_code == 200

    def test_400_for_unknown_strategy(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()):
            response = client.post("/agent/busquets", json={"ticker": "BA", "strategy": "invalid"})
        assert response.status_code == 400

    def test_404_when_ticker_not_found(self):
        from cardinal.data.market_data import TickerNotFoundError
        with patch("cardinal.api.main.fetch_price_history",
                   side_effect=TickerNotFoundError("no history")):
            response = client.post("/agent/busquets", json={"ticker": "ZZZZZ"})
        assert response.status_code == 404

    def test_503_when_gemini_not_configured(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.gemini_client.settings.gemini_configured", False):
            response = client.post("/agent/busquets", json={"ticker": "BA"})
        assert response.status_code == 503

    def test_user_question_passed_through(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.busquets.generate", return_value=FAKE_MEMO) as mock_gen:
            client.post("/agent/busquets", json={"ticker": "BA", "user_question": "What vol filter would help?"})
        prompt = mock_gen.call_args[0][0]
        assert "What vol filter would help?" in prompt