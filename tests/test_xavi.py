"""
Tests for Xavi (Fundamental Agent).

Gemini API is mocked throughout — agent tests verify prompt construction,
snapshot formatting, guardrail integration, and endpoint plumbing.
No real LLM calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cardinal.agents.xavi import build_fundamental_snapshot, run_xavi
from cardinal.api.main import app
from cardinal.core.dcf import FinancialSnapshot
from cardinal.data.market_data import CompanyProfile

client = TestClient(app)

FAKE_SNAPSHOT = FinancialSnapshot(
    ticker="AAPL", free_cash_flow_ttm=99.6e9, net_debt=-56.2e9,
    shares_outstanding=15.4e9, current_price=227.50, beta=1.25,
)
FAKE_PROFILE = CompanyProfile(
    ticker="AAPL", name="Apple Inc.", sector="Technology",
    industry="Consumer Electronics", currency="USD",
    exchange="NMS", market_cap=3.4e12,
)
FAKE_MEMO = (
    "**Valuation Verdict:** Apple trades at a 13% premium to intrinsic value.\n"
    "**Bull Case:** Continued services growth.\n"
    "**Bear Case:** Margin compression.\n"
    "**Key Risks:** High TV dependency.\n"
    "**Peer Comparison:** Inline with peers."
)


# ── snapshot builder ──────────────────────────────────────────────────────────

class TestBuildFundamentalSnapshot:
    def test_contains_ticker(self):
        snap = build_fundamental_snapshot(
            ticker="AAPL", company_name="Apple Inc.", current_price=227.50,
            intrinsic_value=201.40, premium_discount_pct=0.13, wacc=0.092,
            cost_of_equity=0.108, growth_rate=0.08, terminal_growth_rate=0.035,
            projection_years=5, terminal_value_pct_of_ev=0.72,
            enterprise_value=2.16e12, equity_value=2.22e12,
            pv_projected_fcf=[312e9, 320e9, 330e9, 340e9, 350e9],
            pv_terminal_value=1847e9,
        )
        assert "AAPL" in snap
        assert "Apple Inc." in snap
        assert "$227.50" in snap
        assert "$201.40" in snap

    def test_contains_dcf_metrics(self):
        snap = build_fundamental_snapshot(
            ticker="AAPL", company_name="Apple Inc.", current_price=227.50,
            intrinsic_value=201.40, premium_discount_pct=0.13, wacc=0.092,
            cost_of_equity=0.108, growth_rate=0.08, terminal_growth_rate=0.035,
            projection_years=5, terminal_value_pct_of_ev=0.72,
            enterprise_value=2.16e12, equity_value=2.22e12,
            pv_projected_fcf=[312e9], pv_terminal_value=1847e9,
        )
        assert "9.20%" in snap  # WACC
        assert "overvalued" in snap or "undervalued" in snap

    def test_includes_peers_when_provided(self):
        peers = [{"ticker": "MSFT", "ev_ebitda": 24.0, "pe_ratio": 32.0, "ev_revenue": 12.0}]
        snap = build_fundamental_snapshot(
            ticker="AAPL", company_name="Apple Inc.", current_price=227.50,
            intrinsic_value=201.40, premium_discount_pct=0.13, wacc=0.092,
            cost_of_equity=0.108, growth_rate=0.08, terminal_growth_rate=0.035,
            projection_years=5, terminal_value_pct_of_ev=0.72,
            enterprise_value=2.16e12, equity_value=2.22e12,
            pv_projected_fcf=[312e9], pv_terminal_value=1847e9,
            peers=peers, median_ev_ebitda=24.0, median_pe=32.0,
        )
        assert "COMPARABLE COMPANIES" in snap
        assert "MSFT" in snap
        assert "24.0x" in snap

    def test_no_peers_section_when_none(self):
        snap = build_fundamental_snapshot(
            ticker="AAPL", company_name="Apple Inc.", current_price=227.50,
            intrinsic_value=201.40, premium_discount_pct=0.13, wacc=0.092,
            cost_of_equity=0.108, growth_rate=0.08, terminal_growth_rate=0.035,
            projection_years=5, terminal_value_pct_of_ev=0.72,
            enterprise_value=2.16e12, equity_value=2.22e12,
            pv_projected_fcf=[312e9], pv_terminal_value=1847e9,
            peers=None,
        )
        assert "COMPARABLE COMPANIES" not in snap

    def test_undervalued_label_when_negative_premium(self):
        snap = build_fundamental_snapshot(
            ticker="TEST", company_name="Test Co.", current_price=100.0,
            intrinsic_value=150.0, premium_discount_pct=-0.33, wacc=0.09,
            cost_of_equity=0.11, growth_rate=0.08, terminal_growth_rate=0.035,
            projection_years=5, terminal_value_pct_of_ev=0.70,
            enterprise_value=1e9, equity_value=1e9,
            pv_projected_fcf=[100e6], pv_terminal_value=800e6,
        )
        assert "undervalued" in snap


# ── run_xavi ──────────────────────────────────────────────────────────────────

class TestRunXavi:
    def test_calls_gemini_with_cardinal_data(self):
        with patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            result = run_xavi(snapshot="ticker: AAPL\nprice: $227.50")
        mock_gen.assert_called_once()
        call_prompt = mock_gen.call_args[0][0]
        assert "[CARDINAL DATA]" in call_prompt
        assert "AAPL" in call_prompt

    def test_includes_user_question_when_provided(self):
        with patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            run_xavi(snapshot="ticker: AAPL", user_question="What is the bear case?")
        prompt = mock_gen.call_args[0][0]
        assert "What is the bear case?" in prompt
        assert "[USER QUESTION]" in prompt

    def test_includes_news_context_when_provided(self):
        with patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            run_xavi(snapshot="ticker: AAPL", news_context="Apple reports record Q3 revenue")
        prompt = mock_gen.call_args[0][0]
        assert "[NEWS CONTEXT" in prompt
        assert "record Q3 revenue" in prompt

    def test_returns_memo_text(self):
        with patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO):
            result = run_xavi(snapshot="ticker: AAPL")
        assert result == FAKE_MEMO

    def test_default_task_prompt_when_no_question(self):
        with patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            run_xavi(snapshot="ticker: AAPL")
        prompt = mock_gen.call_args[0][0]
        assert "[TASK]" in prompt


# ── API endpoint ──────────────────────────────────────────────────────────────

class TestXaviEndpoint:
    def test_returns_200_with_memo(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE), \
             patch("cardinal.api.main.settings.fmp_configured", False), \
             patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO):
            response = client.post("/agent/xavi", json={"ticker": "AAPL"})
        assert response.status_code == 200
        body = response.json()
        assert body["agent"] == "xavi"
        assert body["ticker"] == "AAPL"
        assert body["memo"] == FAKE_MEMO

    def test_404_when_ticker_not_found(self):
        from cardinal.data.market_data import TickerNotFoundError
        with patch("cardinal.api.main.fetch_financial_snapshot",
                   side_effect=TickerNotFoundError("not found")):
            response = client.post("/agent/xavi", json={"ticker": "ZZZZZ"})
        assert response.status_code == 404

    def test_503_when_gemini_not_configured(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE), \
             patch("cardinal.api.main.settings.fmp_configured", False), \
             patch("cardinal.agents.gemini_client.settings.gemini_configured", False):
            response = client.post("/agent/xavi", json={"ticker": "AAPL"})
        assert response.status_code == 503

    def test_custom_assumptions_passed_through(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE), \
             patch("cardinal.api.main.settings.fmp_configured", False), \
             patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            client.post("/agent/xavi", json={
                "ticker": "AAPL", "growth_rate": 0.12, "wacc_override": 0.10
            })
        # Verify the prompt passed to Gemini contains the custom growth rate
        prompt = mock_gen.call_args[0][0]
        assert "12.0%" in prompt

    def test_user_question_passed_through(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE), \
             patch("cardinal.api.main.settings.fmp_configured", False), \
             patch("cardinal.agents.xavi.generate", return_value=FAKE_MEMO) as mock_gen:
            client.post("/agent/xavi", json={"ticker": "AAPL", "user_question": "What about the bear case?"})
        prompt = mock_gen.call_args[0][0]
        assert "What about the bear case?" in prompt