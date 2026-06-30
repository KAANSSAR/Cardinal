"""Shared fixtures for the Cardinal test suite."""

import pytest

from cardinal.core.dcf import DCFAssumptions, FinancialSnapshot


@pytest.fixture
def aapl_snapshot() -> FinancialSnapshot:
    """Representative large-cap snapshot, roughly AAPL-shaped figures."""
    return FinancialSnapshot(
        ticker="AAPL",
        free_cash_flow_ttm=99.6e9,
        net_debt=-56.2e9,  # net cash position
        shares_outstanding=15.4e9,
        current_price=227.50,
        beta=1.25,
        risk_free_rate=0.042,
        market_risk_premium=0.055,
        cost_of_debt=0.045,
        tax_rate=0.21,
    )


@pytest.fixture
def base_assumptions() -> DCFAssumptions:
    return DCFAssumptions(
        growth_rate=0.08,
        terminal_growth_rate=0.035,
        projection_years=5,
    )
