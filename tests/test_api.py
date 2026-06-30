"""
API-level tests — exercise the FastAPI app through TestClient.

The data layer (yfinance) is mocked here too, same principle as
test_market_data.py: these are integration tests for our own routing,
validation, and error-handling logic, not tests of Yahoo Finance's
uptime.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cardinal.api.main import app
from cardinal.core.dcf import FinancialSnapshot
from cardinal.data.fmp_client import FMPNotConfiguredError
from cardinal.data.fmp_client import TickerNotFoundError as FMPTickerNotFoundError
from cardinal.data.market_data import (
    CompanyProfile,
    InsufficientDataError,
    TickerNotFoundError,
)

client = TestClient(app)

FAKE_SNAPSHOT = FinancialSnapshot(
    ticker="AAPL", free_cash_flow_ttm=99.6e9, net_debt=-56.2e9,
    shares_outstanding=15.4e9, current_price=227.50, beta=1.25,
)
FAKE_PROFILE = CompanyProfile(
    ticker="AAPL", name="Apple Inc.", sector="Technology", industry="Consumer Electronics",
    currency="USD", exchange="NMS", market_cap=3.4e12,
)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class TestDCFEndpoint:
    def test_returns_200_with_valid_ticker(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            response = client.get("/ticker/AAPL/dcf")
        assert response.status_code == 200

    def test_response_contains_expected_fields(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            response = client.get("/ticker/AAPL/dcf")
        body = response.json()
        expected_keys = {
            "ticker", "company_name", "wacc", "cost_of_equity", "projected_fcf",
            "pv_projected_fcf", "pv_terminal_value", "terminal_value_pct_of_ev",
            "enterprise_value", "equity_value", "intrinsic_value_per_share",
            "current_price", "premium_discount_pct",
        }
        assert expected_keys.issubset(body.keys())
        assert body["ticker"] == "AAPL"
        assert body["company_name"] == "Apple Inc."

    def test_query_params_change_output(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            low = client.get("/ticker/AAPL/dcf", params={"wacc_override": 0.08, "terminal_growth_rate": 0.03})
            high = client.get("/ticker/AAPL/dcf", params={"wacc_override": 0.14, "terminal_growth_rate": 0.03})
        assert low.json()["intrinsic_value_per_share"] > high.json()["intrinsic_value_per_share"]

    def test_404_when_ticker_not_found(self):
        with patch(
            "cardinal.api.main.fetch_financial_snapshot",
            side_effect=TickerNotFoundError("No data for 'ZZZZZ'"),
        ):
            response = client.get("/ticker/ZZZZZ/dcf")
        assert response.status_code == 404

    def test_422_when_insufficient_data(self):
        with patch(
            "cardinal.api.main.fetch_financial_snapshot",
            side_effect=InsufficientDataError("Missing free_cash_flow"),
        ):
            response = client.get("/ticker/WEIRDTICKER/dcf")
        assert response.status_code == 422

    def test_400_when_wacc_not_greater_than_terminal_growth(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            response = client.get(
                "/ticker/AAPL/dcf",
                params={"wacc_override": 0.03, "terminal_growth_rate": 0.03},
            )
        assert response.status_code == 400

    def test_projection_years_out_of_range_rejected_by_pydantic(self):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            response = client.get("/ticker/AAPL/dcf", params={"projection_years": 50})
        # FastAPI/pydantic should reject this before it ever reaches run_dcf
        assert response.status_code == 422

    @pytest.mark.parametrize("growth_rate", [-0.1, 0.0, 0.05, 0.15, 0.30])
    def test_accepts_range_of_growth_rates(self, growth_rate):
        with patch("cardinal.api.main.fetch_financial_snapshot", return_value=FAKE_SNAPSHOT), \
             patch("cardinal.api.main.fetch_company_profile", return_value=FAKE_PROFILE):
            response = client.get("/ticker/AAPL/dcf", params={"growth_rate": growth_rate})
        assert response.status_code == 200


class TestPriceHistoryEndpoint:
    def _fake_history(self):
        index = pd.to_datetime(["2026-01-02", "2026-01-03"])
        return pd.DataFrame(
            {
                "Open": [225.0, 227.0],
                "High": [228.0, 230.0],
                "Low": [224.0, 226.0],
                "Close": [227.0, 229.0],
                "Volume": [50_000_000, 48_000_000],
            },
            index=index,
        )

    def test_returns_200_with_points(self):
        with patch("cardinal.api.main.fetch_price_history", return_value=self._fake_history()):
            response = client.get("/ticker/AAPL/price-history")
        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert len(body["points"]) == 2
        assert body["points"][0]["close"] == 227.0

    def test_404_when_ticker_not_found(self):
        with patch(
            "cardinal.api.main.fetch_price_history",
            side_effect=TickerNotFoundError("No price history for 'ZZZZZ'"),
        ):
            response = client.get("/ticker/ZZZZZ/price-history")
        assert response.status_code == 404

    def test_period_and_interval_passed_through(self):
        with patch(
            "cardinal.api.main.fetch_price_history", return_value=self._fake_history()
        ) as mock_fetch:
            client.get("/ticker/AAPL/price-history", params={"period": "1y", "interval": "1wk"})
        mock_fetch.assert_called_once_with("AAPL", period="1y", interval="1wk")


class TestIncomeStatementEndpoint:
    def test_returns_200_with_statements(self):
        fake_statements = [{"revenue": 391e9, "netIncome": 93e9}]
        with patch("cardinal.api.main.get_income_statement", return_value=fake_statements):
            response = client.get("/ticker/AAPL/income-statement")
        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["statements"][0]["revenue"] == 391e9

    def test_503_when_fmp_not_configured(self):
        with patch(
            "cardinal.api.main.get_income_statement",
            side_effect=FMPNotConfiguredError("FMP_API_KEY is not set"),
        ):
            response = client.get("/ticker/AAPL/income-statement")
        assert response.status_code == 503

    def test_404_when_ticker_not_found(self):
        with patch(
            "cardinal.api.main.get_income_statement",
            side_effect=FMPTickerNotFoundError("No FMP income statement for 'ZZZZZ'"),
        ):
            response = client.get("/ticker/ZZZZZ/income-statement")
        assert response.status_code == 404

    def test_limit_param_passed_through(self):
        with patch(
            "cardinal.api.main.get_income_statement", return_value=[{}]
        ) as mock_fetch:
            client.get("/ticker/AAPL/income-statement", params={"limit": 5})
        mock_fetch.assert_called_once_with("AAPL", limit=5)

    def test_502_when_fmp_request_fails(self):
        from cardinal.data.fmp_client import FMPRequestError
        with patch(
            "cardinal.api.main.get_income_statement",
            side_effect=FMPRequestError("FMP returned status 500"),
        ):
            response = client.get("/ticker/AAPL/income-statement")
        assert response.status_code == 502


class TestBalanceSheetEndpoint:
    def test_returns_200_with_statements(self):
        fake_statements = [{"totalDebt": 100e9, "totalEquity": 60e9}]
        with patch("cardinal.api.main.get_balance_sheet_statement", return_value=fake_statements):
            response = client.get("/ticker/AAPL/balance-sheet")
        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["statements"][0]["totalDebt"] == 100e9

    def test_503_when_fmp_not_configured(self):
        with patch(
            "cardinal.api.main.get_balance_sheet_statement",
            side_effect=FMPNotConfiguredError("FMP_API_KEY is not set"),
        ):
            response = client.get("/ticker/AAPL/balance-sheet")
        assert response.status_code == 503

    def test_404_when_ticker_not_found(self):
        with patch(
            "cardinal.api.main.get_balance_sheet_statement",
            side_effect=FMPTickerNotFoundError("No FMP balance sheet for 'ZZZZZ'"),
        ):
            response = client.get("/ticker/ZZZZZ/balance-sheet")
        assert response.status_code == 404

    def test_limit_param_passed_through(self):
        with patch(
            "cardinal.api.main.get_balance_sheet_statement", return_value=[{}]
        ) as mock_fetch:
            client.get("/ticker/AAPL/balance-sheet", params={"limit": 2})
        mock_fetch.assert_called_once_with("AAPL", limit=2)

    def test_502_when_fmp_request_fails(self):
        from cardinal.data.fmp_client import FMPRequestError
        with patch(
            "cardinal.api.main.get_balance_sheet_statement",
            side_effect=FMPRequestError("FMP returned status 500"),
        ):
            response = client.get("/ticker/AAPL/balance-sheet")
        assert response.status_code == 502
