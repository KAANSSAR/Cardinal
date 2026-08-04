"""Tests for Iniesta (Quantitative Analyst Agent)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from cardinal.agents import cache as agent_cache

from cardinal.agents.iniesta import build_quant_snapshot, run_iniesta
from cardinal.api.main import app

client = TestClient(app)

FAKE_MEMO = (
    "**Signal Bias:** BULLISH (Moderate confidence) — momentum is constructive across all timeframes.\n"
    "**Momentum Analysis:** Short-term momentum is positive at 0.58...\n"
    "**Risk Metrics:** Rolling Sharpe 252d of 1.75 indicates strong risk-adjusted returns.\n"
    "**Volatility Regime:** Near-term vol (31.8%) is elevated vs long-run (24.8%).\n"
    "**Technical Positioning:** RSI at 65.2 — approaching but not overbought.\n"
    "**Timing Commentary:** Constructive entry but monitor vol expansion."
)

SAMPLE_SNAP_KWARGS = dict(
    ticker="AAPL", current_price=333.02, benchmark="^GSPC",
    momentum_20d=0.5767, momentum_60d=0.812, momentum_252d=2.2777,
    sharpe_60d=3.0369, sharpe_252d=1.7538, beta=0.877,
    vol_10d=0.3184, vol_30d=0.3355, vol_60d=0.2879, vol_252d=0.2477,
    rsi=65.24, bb_upper=346.36, bb_middle=314.39, bb_lower=282.41, bb_pct_b=0.7914,
)


class TestBuildQuantSnapshot:
    def test_contains_ticker(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "AAPL" in snap

    def test_contains_momentum_scores(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Momentum 20d" in snap
        assert "Momentum 60d" in snap
        assert "Momentum 252d" in snap

    def test_contains_sharpe_ratios(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "Sharpe" in snap

    def test_contains_volatility_surface(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "10d vol" in snap
        assert "252d vol" in snap

    def test_contains_rsi_and_bollinger(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "RSI" in snap
        assert "Bollinger" in snap

    def test_bullish_label_for_strong_momentum(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "BULLISH" in snap  # momentum_252d=2.28 > 0.3

    def test_elevated_vol_flagged(self):
        # vol_10d=0.40 vs vol_252d=0.20 — near-term > long-run, so surface is INVERTED
        snap = build_quant_snapshot(
            **{**SAMPLE_SNAP_KWARGS, "vol_10d": 0.40, "vol_252d": 0.20}
        )
        assert "INVERTED" in snap

    def test_handles_none_values(self):
        snap = build_quant_snapshot(
            **{**SAMPLE_SNAP_KWARGS, "beta": None, "rsi": None, "bb_pct_b": None}
        )
        assert "N/A" in snap

    def test_benchmark_included(self):
        snap = build_quant_snapshot(**SAMPLE_SNAP_KWARGS)
        assert "^GSPC" in snap


class TestRunIniesta:
    def test_calls_gemini_with_cardinal_data(self):
        with patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO) as mock_gen:
            run_iniesta(snapshot="ticker: AAPL\nRSI: 65.2")
        prompt = mock_gen.call_args[0][0]
        assert "[CARDINAL DATA]" in prompt

    def test_includes_user_question_when_provided(self):
        with patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO) as mock_gen:
            run_iniesta(snapshot="ticker: AAPL", user_question="Is the vol elevated?")
        prompt = mock_gen.call_args[0][0]
        assert "Is the vol elevated?" in prompt
        assert "[USER QUESTION]" in prompt

    def test_includes_news_context_when_provided(self):
        with patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO) as mock_gen:
            run_iniesta(snapshot="ticker: AAPL", news_context="Apple reports record Q3")
        prompt = mock_gen.call_args[0][0]
        assert "[NEWS CONTEXT" in prompt
        assert "record Q3" in prompt

    def test_returns_memo_text(self):
        with patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO):
            result = run_iniesta(snapshot="ticker: AAPL")
        assert result == FAKE_MEMO

    def test_default_task_when_no_question(self):
        with patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO) as mock_gen:
            run_iniesta(snapshot="ticker: AAPL")
        prompt = mock_gen.call_args[0][0]
        assert "[TASK]" in prompt


class TestIniestaEndpoint:
    def setup_method(self):
        agent_cache.clear()

    def _fake_history(self):
        import pandas as pd
        import numpy as np
        np.random.seed(42)
        n = 756
        dates = pd.date_range("2021-01-04", periods=n, freq="B")
        returns = np.random.normal(0.0004, 0.015, n)
        prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)
        df = pd.DataFrame({"Close": prices, "Open": prices, "High": prices * 1.01,
                           "Low": prices * 0.99, "Volume": 1_000_000})
        return df

    def test_returns_200_with_memo(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO):
            response = client.post("/agent/iniesta", json={"ticker": "AAPL"})
        assert response.status_code == 200
        body = response.json()
        assert body["agent"] == "iniesta"
        assert body["ticker"] == "AAPL"
        assert body["memo"] == FAKE_MEMO

    def test_404_when_ticker_not_found(self):
        from cardinal.data.market_data import TickerNotFoundError
        with patch("cardinal.api.main.fetch_price_history",
                   side_effect=TickerNotFoundError("no history")):
            response = client.post("/agent/iniesta", json={"ticker": "ZZZZZ"})
        assert response.status_code == 404

    def test_503_when_gemini_not_configured(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.gemini_client.settings.gemini_configured", False):
            response = client.post("/agent/iniesta", json={"ticker": "AAPL"})
        assert response.status_code == 503

    def test_user_question_passed_through(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()), \
             patch("cardinal.agents.iniesta.generate", return_value=FAKE_MEMO) as mock_gen:
            client.post("/agent/iniesta", json={"ticker": "AAPL", "user_question": "Is momentum diverging?"})
        prompt = mock_gen.call_args[0][0]
        assert "Is momentum diverging?" in prompt