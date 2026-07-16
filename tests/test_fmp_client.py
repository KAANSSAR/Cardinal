"""
Tests for the FMP client.

httpx is mocked throughout — same principle as test_market_data.py.
We also test the FMPNotConfiguredError path explicitly, since a missing
API key is a real failure mode this module needs to handle gracefully.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from cardinal.data.fmp_client import (
    FMPNotConfiguredError,
    FMPRequestError,
    InsufficientDataError,
    TickerNotFoundError,
    fetch_company_profile,
    fetch_financial_snapshot,
    get_balance_sheet_statement,
    get_cash_flow_statement,
    get_income_statement,
    get_profile,
    get_quote,
)

FAKE_PROFILE = [{
    "symbol": "AAPL",
    "companyName": "Apple Inc.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "currency": "USD",
    "exchangeShortName": "NASDAQ",
    "marketCap": 3.4e12,
    "price": 227.50,
    "beta": 1.25,
    "sharesOutstanding": 15.4e9,
}]

FAKE_CASH_FLOW = [{"freeCashFlow": 99.6e9}]
FAKE_BALANCE_SHEET = [{"totalDebt": 100e9, "cashAndCashEquivalents": 156.2e9}]


def _mock_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


@pytest.fixture(autouse=True)
def fmp_key_configured(monkeypatch):
    """Ensure every test in this file runs as if FMP_API_KEY is set, unless overridden."""
    monkeypatch.setattr("cardinal.data.fmp_client.settings.fmp_api_key", "fake_test_key")
    monkeypatch.setattr("cardinal.data.fmp_client.settings.fmp_configured", True)


class TestNotConfigured:
    def test_raises_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr("cardinal.data.fmp_client.settings.fmp_api_key", None)
        monkeypatch.setattr("cardinal.data.fmp_client.settings.fmp_configured", False)
        with pytest.raises(FMPNotConfiguredError):
            get_profile("AAPL")


class TestGetProfile:
    def test_parses_profile_list_response(self):
        with patch("httpx.get", return_value=_mock_response(FAKE_PROFILE)):
            profile = get_profile("AAPL")
        assert profile["companyName"] == "Apple Inc."

    def test_raises_on_empty_response(self):
        with patch("httpx.get", return_value=_mock_response([])):
            with pytest.raises(TickerNotFoundError):
                get_profile("ZZZZZ")

    def test_raises_on_non_200_status(self):
        with patch("httpx.get", return_value=_mock_response({}, status_code=403)):
            with pytest.raises(FMPRequestError, match="403"):
                get_profile("AAPL")

    def test_raises_on_fmp_error_message(self):
        with patch("httpx.get", return_value=_mock_response({"Error Message": "Invalid API key"})):
            with pytest.raises(TickerNotFoundError):
                get_profile("AAPL")


class TestGetQuote:
    def test_parses_quote(self):
        fake_quote = [{"symbol": "AAPL", "price": 227.50}]
        with patch("httpx.get", return_value=_mock_response(fake_quote)):
            quote = get_quote("AAPL")
        assert quote["price"] == 227.50

    def test_raises_on_empty_quote(self):
        with patch("httpx.get", return_value=_mock_response([])):
            with pytest.raises(TickerNotFoundError):
                get_quote("ZZZZZ")


class TestNetworkErrors:
    def test_raises_fmp_request_error_on_connection_failure(self):
        import httpx as httpx_module
        with patch("httpx.get", side_effect=httpx_module.ConnectError("connection refused")):
            with pytest.raises(FMPRequestError, match="Network error"):
                get_profile("AAPL")


class TestFinancialStatements:
    def test_income_statement_returns_list(self):
        fake_income = [{"revenue": 391e9}, {"revenue": 383e9}]
        with patch("httpx.get", return_value=_mock_response(fake_income)):
            result = get_income_statement("AAPL", limit=2)
        assert len(result) == 2

    def test_income_statement_raises_on_empty(self):
        with patch("httpx.get", return_value=_mock_response([])):
            with pytest.raises(TickerNotFoundError):
                get_income_statement("ZZZZZ")

    def test_balance_sheet_returns_list(self):
        with patch("httpx.get", return_value=_mock_response(FAKE_BALANCE_SHEET)):
            result = get_balance_sheet_statement("AAPL")
        assert result[0]["totalDebt"] == 100e9

    def test_balance_sheet_raises_on_empty(self):
        with patch("httpx.get", return_value=_mock_response([])):
            with pytest.raises(TickerNotFoundError):
                get_balance_sheet_statement("ZZZZZ")

    def test_cash_flow_returns_list(self):
        with patch("httpx.get", return_value=_mock_response(FAKE_CASH_FLOW)):
            result = get_cash_flow_statement("AAPL")
        assert result[0]["freeCashFlow"] == 99.6e9

    def test_cash_flow_raises_on_empty(self):
        with patch("httpx.get", return_value=_mock_response([])):
            with pytest.raises(TickerNotFoundError):
                get_cash_flow_statement("ZZZZZ")


class TestFetchCompanyProfile:
    def test_parses_full_profile(self):
        with patch("httpx.get", return_value=_mock_response(FAKE_PROFILE)):
            profile = fetch_company_profile("AAPL")
        assert profile.ticker == "AAPL"
        assert profile.name == "Apple Inc."
        assert profile.sector == "Technology"
        assert profile.beta == 1.25


class TestFetchFinancialSnapshot:
    def _patched_get(self, resource: str, *args, **kwargs):
        mapping = {
            "profile": FAKE_PROFILE,
            "cash-flow-statement": FAKE_CASH_FLOW,
            "balance-sheet-statement": FAKE_BALANCE_SHEET,
        }
        return _mock_response(mapping[resource])

    def test_parses_full_snapshot(self):
        def fake_httpx_get(url, params=None, **kwargs):
            resource = url.rsplit("/", 1)[-1]
            return self._patched_get(resource)

        with patch("httpx.get", side_effect=fake_httpx_get):
            snapshot = fetch_financial_snapshot("AAPL")

        assert snapshot.ticker == "AAPL"
        assert math.isclose(snapshot.free_cash_flow_ttm, 99.6e9)
        assert math.isclose(snapshot.current_price, 227.50)
        assert math.isclose(snapshot.beta, 1.25)

    def test_net_debt_computed_correctly(self):
        def fake_httpx_get(url, params=None, **kwargs):
            resource = url.rsplit("/", 1)[-1]
            return self._patched_get(resource)

        with patch("httpx.get", side_effect=fake_httpx_get):
            snapshot = fetch_financial_snapshot("AAPL")

        # totalDebt=100e9, cash=156.2e9 -> net_debt = -56.2e9
        assert math.isclose(snapshot.net_debt, -56.2e9, rel_tol=1e-6)

    def test_raises_when_missing_free_cash_flow(self):
        empty_cash_flow = [{}]

        def fake_httpx_get(url, params=None, **kwargs):
            resource = url.rsplit("/", 1)[-1]
            if resource == "cash-flow-statement":
                return _mock_response(empty_cash_flow)
            return self._patched_get(resource)

        with patch("httpx.get", side_effect=fake_httpx_get):
            with pytest.raises(InsufficientDataError, match="free_cash_flow"):
                fetch_financial_snapshot("AAPL")

    def test_missing_beta_defaults_to_one(self):
        profile_no_beta = [{**FAKE_PROFILE[0]}]
        del profile_no_beta[0]["beta"]

        def fake_httpx_get(url, params=None, **kwargs):
            resource = url.rsplit("/", 1)[-1]
            if resource == "profile":
                return _mock_response(profile_no_beta)
            return self._patched_get(resource)

        with patch("httpx.get", side_effect=fake_httpx_get):
            snapshot = fetch_financial_snapshot("AAPL")

        assert snapshot.beta == 1.0
