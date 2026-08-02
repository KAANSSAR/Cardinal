"""Tests for Messi (Synthesis Agent) — orchestrating version."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cardinal.agents.messi import build_synthesis_snapshot, run_messi
from cardinal.api.main import app
from cardinal.core.dcf import FinancialSnapshot
from cardinal.data.market_data import CompanyProfile

client = TestClient(app)

XAVI_MEMO = "**Valuation Verdict:** AAPL overvalued at 125% premium.\n**Bull Case:** Services.\n**Bear Case:** FCF compression.\n**Key Risks:** TV dependency.\n**Peer Comparison:** Premium to peers."
INIESTA_MEMO = "**Signal Bias:** BULLISH moderate.\n**Momentum Analysis:** Strong 252d.\n**Risk Metrics:** Sharpe 1.49.\n**Volatility Regime:** Vol elevated.\n**Technical Positioning:** RSI 43.\n**Timing Commentary:** Wait for vol."
BUSQUETS_MEMO = "**Strategy Verdict:** No edge.\n**Performance Analysis:** -12.6% vs +85.7%.\n**Drawdown Assessment:** -27.1%.\n**Regime Observations:** Loses in trends.\n**Suggested Refinements:** Vol filter.\n**Risk Flag:** 5 trades only."
FAKE_VERDICT = "**Synthesis Verdict [HOLD]:** HOLD — overvaluation conflicts with bullish quant signals.\n\n**Confidence: [MODERATE]** — Conflicting signals."

FAKE_SNAPSHOT = FinancialSnapshot(
    ticker="AAPL", free_cash_flow_ttm=99.6e9, net_debt=-56.2e9,
    shares_outstanding=15.4e9, current_price=227.50, beta=1.25,
)
FAKE_PROFILE = CompanyProfile(
    ticker="AAPL", name="Apple Inc.", sector="Technology",
    industry="Consumer Electronics", currency="USD", exchange="NMS", market_cap=3.4e12,
)


def _fake_history():
    np.random.seed(42)
    n = 756
    dates = pd.date_range("2021-01-04", periods=n, freq="B")
    returns = np.random.normal(0.0004, 0.015, n)
    prices = pd.Series(100 * np.exp(np.cumsum(returns)), index=dates)
    return pd.DataFrame({
        "Close": prices, "Open": prices,
        "High": prices * 1.01, "Low": prices * 0.99, "Volume": 1_000_000
    })


# ── snapshot builder (unchanged) ─────────────────────────────────────────────

class TestBuildSynthesisSnapshot:
    def test_contains_all_three_agents(self):
        snap = build_synthesis_snapshot("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO)
        assert "XAVI" in snap
        assert "INIESTA" in snap
        assert "BUSQUETS" in snap

    def test_contains_ticker(self):
        snap = build_synthesis_snapshot("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO)
        assert "AAPL" in snap

    def test_memos_in_correct_order(self):
        snap = build_synthesis_snapshot("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO)
        assert snap.index("XAVI") < snap.index("INIESTA") < snap.index("BUSQUETS")


# ── run_messi (unchanged) ─────────────────────────────────────────────────────

class TestRunMessi:
    def test_calls_gemini_with_all_memos(self):
        with patch("cardinal.agents.messi.generate", return_value=FAKE_VERDICT) as mock_gen:
            run_messi("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO)
        prompt = mock_gen.call_args[0][0]
        assert "XAVI" in prompt and "INIESTA" in prompt and "BUSQUETS" in prompt

    def test_user_question_included(self):
        with patch("cardinal.agents.messi.generate", return_value=FAKE_VERDICT) as mock_gen:
            run_messi("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO, user_question="Is this a buy?")
        assert "Is this a buy?" in mock_gen.call_args[0][0]

    def test_returns_verdict(self):
        with patch("cardinal.agents.messi.generate", return_value=FAKE_VERDICT):
            assert run_messi("AAPL", XAVI_MEMO, INIESTA_MEMO, BUSQUETS_MEMO) == FAKE_VERDICT


# ── orchestrating endpoint ────────────────────────────────────────────────────

class TestMessiEndpoint:
    def setup_method(self):
        from cardinal.agents import cache as agent_cache
        agent_cache.clear()
    def _patch_all(self, verdict=FAKE_VERDICT):
        return [
            patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT),
            patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE),
            patch("cardinal.api.main.settings.fmp_configured", False),
            patch("cardinal.api.main.fetch_price_history", return_value=_fake_history()),
            patch("cardinal.agents.xavi.generate", return_value=XAVI_MEMO),
            patch("cardinal.agents.iniesta.generate", return_value=INIESTA_MEMO),
            patch("cardinal.agents.busquets.generate", return_value=BUSQUETS_MEMO),
            patch("cardinal.agents.messi.generate", return_value=verdict),
        ]

    def test_returns_all_four_memos(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={"ticker": "AAPL"})
        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["xavi_memo"] == XAVI_MEMO
        assert body["iniesta_memo"] == INIESTA_MEMO
        assert body["busquets_memo"] == BUSQUETS_MEMO
        assert body["synthesis_memo"] == FAKE_VERDICT
        assert "cached_agents" in body

    def test_cached_agents_empty_on_first_call(self):
        from cardinal.agents import cache as agent_cache
        agent_cache.clear()
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={"ticker": "MSFT"})
        assert response.json()["cached_agents"] == []

    def test_agents_served_from_cache_on_second_call(self):
        from cardinal.agents import cache as agent_cache
        agent_cache.clear()
        patches = self._patch_all()
        # First call — populates cache
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            client.post("/agent/messi", json={"ticker": "TSLA"})
        # Second call — all three individual agents should come from cache
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={"ticker": "TSLA"})
        cached = response.json()["cached_agents"]
        assert "xavi" in cached
        assert "iniesta" in cached
        assert "busquets" in cached

    def test_404_when_ticker_not_found(self):
        from cardinal.data.market_data import TickerNotFoundError
        with patch("cardinal.api.main.fetch_financial_snapshot",
                   side_effect=TickerNotFoundError("not found")):
            response = client.post("/agent/messi", json={"ticker": "ZZZZZ"})
        assert response.status_code == 404

    def test_503_when_gemini_not_configured(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE), \
             patch("cardinal.api.main.settings.fmp_configured", False), \
             patch("cardinal.api.main.fetch_price_history", return_value=_fake_history()), \
             patch("cardinal.agents.gemini_client.settings.gemini_configured", False):
            response = client.post("/agent/messi", json={"ticker": "AAPL"})
        assert response.status_code == 503

    def test_ticker_uppercased(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={"ticker": "aapl"})
        assert response.json()["ticker"] == "AAPL"

    def test_custom_dcf_assumptions_accepted(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={
                "ticker": "AAPL", "growth_rate": 0.12, "wacc_override": 0.10
            })
        assert response.status_code == 200

    def test_mean_reversion_strategy_accepted(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3], \
             patches[4], patches[5], patches[6], patches[7]:
            response = client.post("/agent/messi", json={
                "ticker": "AAPL", "strategy": "mean_reversion"
            })
        assert response.status_code == 200