"""
Tests for the DCF valuation engine.

Covers: known-value checks against hand-calculated figures, monotonicity
properties (higher WACC -> lower value, higher growth -> higher value),
edge cases, and input validation.
"""

from __future__ import annotations

import math

import pytest

from cardinal.core.dcf import (
    DCFAssumptions,
    FinancialSnapshot,
    compute_cost_of_equity,
    compute_wacc,
    discount_to_present_value,
    project_free_cash_flows,
    run_dcf,
    terminal_value_gordon_growth,
)


# ── CAPM / cost of equity ────────────────────────────────────────────────

class TestCostOfEquity:
    def test_known_value(self):
        # r_e = 0.04 + 1.2 * 0.055 = 0.106
        result = compute_cost_of_equity(beta=1.2, risk_free_rate=0.04, market_risk_premium=0.055)
        assert math.isclose(result, 0.106, rel_tol=1e-9)

    def test_beta_zero_equals_risk_free_rate(self):
        result = compute_cost_of_equity(beta=0.0, risk_free_rate=0.04, market_risk_premium=0.055)
        assert math.isclose(result, 0.04)

    def test_higher_beta_increases_cost_of_equity(self):
        low = compute_cost_of_equity(beta=0.8, risk_free_rate=0.04, market_risk_premium=0.055)
        high = compute_cost_of_equity(beta=1.5, risk_free_rate=0.04, market_risk_premium=0.055)
        assert high > low


# ── WACC ──────────────────────────────────────────────────────────────────

class TestWACC:
    def test_all_equity_wacc_equals_cost_of_equity(self):
        snapshot = FinancialSnapshot(
            ticker="TEST", free_cash_flow_ttm=1e9, net_debt=0.0,
            shares_outstanding=1e8, current_price=100.0, beta=1.0,
            total_debt=0.0,
        )
        wacc = compute_wacc(snapshot)
        cost_of_equity = compute_cost_of_equity(1.0, snapshot.risk_free_rate, snapshot.market_risk_premium)
        assert math.isclose(wacc, cost_of_equity, rel_tol=1e-9)

    def test_wacc_between_cost_of_debt_and_equity(self, aapl_snapshot):
        wacc = compute_wacc(aapl_snapshot)
        cost_of_equity = compute_cost_of_equity(
            aapl_snapshot.beta, aapl_snapshot.risk_free_rate, aapl_snapshot.market_risk_premium
        )
        after_tax_kd = aapl_snapshot.cost_of_debt * (1 - aapl_snapshot.tax_rate)
        assert after_tax_kd <= wacc <= cost_of_equity or wacc == cost_of_equity

    def test_higher_debt_weight_pulls_wacc_toward_cost_of_debt(self):
        low_debt = FinancialSnapshot(
            ticker="A", free_cash_flow_ttm=1e9, net_debt=0.0, shares_outstanding=1e8,
            current_price=100.0, beta=1.2, total_debt=1e8,  # small debt
        )
        high_debt = FinancialSnapshot(
            ticker="B", free_cash_flow_ttm=1e9, net_debt=0.0, shares_outstanding=1e8,
            current_price=100.0, beta=1.2, total_debt=8e9,  # large debt relative to equity
        )
        assert compute_wacc(high_debt) < compute_wacc(low_debt)

    def test_zero_total_capital_raises(self):
        snapshot = FinancialSnapshot(
            ticker="ZERO", free_cash_flow_ttm=1e9, net_debt=0.0,
            shares_outstanding=1e8, current_price=0.0, beta=1.0, total_debt=0.0,
        )
        with pytest.raises(ValueError, match="Total capital"):
            compute_wacc(snapshot)


# ── FCF projection & discounting ─────────────────────────────────────────

class TestProjection:
    def test_known_projection_values(self):
        result = project_free_cash_flows(fcf_base=100.0, growth_rate=0.10, years=3)
        expected = [110.0, 121.0, 133.1]
        for actual, exp in zip(result, expected):
            assert math.isclose(actual, exp, rel_tol=1e-9)

    def test_zero_growth_is_flat(self):
        result = project_free_cash_flows(fcf_base=50.0, growth_rate=0.0, years=4)
        assert all(math.isclose(v, 50.0) for v in result)

    def test_correct_length(self):
        result = project_free_cash_flows(fcf_base=10.0, growth_rate=0.05, years=7)
        assert len(result) == 7


class TestDiscounting:
    def test_known_discount_values(self):
        # CF=110 at t=1, r=10% -> PV=100
        result = discount_to_present_value([110.0], discount_rate=0.10)
        assert math.isclose(result[0], 100.0, rel_tol=1e-9)

    def test_zero_rate_no_discounting(self):
        result = discount_to_present_value([100.0, 200.0], discount_rate=0.0)
        assert result == [100.0, 200.0]

    def test_later_cash_flows_worth_less(self):
        flows = [100.0, 100.0, 100.0]
        pv = discount_to_present_value(flows, discount_rate=0.08)
        assert pv[0] > pv[1] > pv[2]


# ── Terminal value ────────────────────────────────────────────────────────

class TestTerminalValue:
    def test_known_value(self):
        # TV = 100 * 1.03 / (0.09 - 0.03) = 1716.67
        tv = terminal_value_gordon_growth(final_year_fcf=100.0, wacc=0.09, terminal_growth_rate=0.03)
        assert math.isclose(tv, 1716.666667, rel_tol=1e-6)

    def test_raises_when_wacc_equals_growth(self):
        with pytest.raises(ValueError, match="must exceed"):
            terminal_value_gordon_growth(100.0, wacc=0.05, terminal_growth_rate=0.05)

    def test_raises_when_wacc_below_growth(self):
        with pytest.raises(ValueError, match="must exceed"):
            terminal_value_gordon_growth(100.0, wacc=0.03, terminal_growth_rate=0.05)


# ── Full DCF pipeline ─────────────────────────────────────────────────────

class TestRunDCF:
    def test_returns_consistent_equity_value(self, aapl_snapshot, base_assumptions):
        result = run_dcf(aapl_snapshot, base_assumptions)
        assert math.isclose(
            result.equity_value,
            result.enterprise_value - aapl_snapshot.net_debt,
            rel_tol=1e-9,
        )

    def test_intrinsic_value_per_share_consistency(self, aapl_snapshot, base_assumptions):
        result = run_dcf(aapl_snapshot, base_assumptions)
        assert math.isclose(
            result.intrinsic_value_per_share,
            result.equity_value / aapl_snapshot.shares_outstanding,
            rel_tol=1e-9,
        )

    def test_terminal_value_majority_of_enterprise_value(self, aapl_snapshot, base_assumptions):
        # Standard DCF behaviour: TV typically dominates EV (60-90% range)
        result = run_dcf(aapl_snapshot, base_assumptions)
        assert 0.5 < result.terminal_value_pct_of_ev < 0.95

    def test_higher_wacc_reduces_intrinsic_value(self, aapl_snapshot):
        low_wacc = run_dcf(aapl_snapshot, DCFAssumptions(wacc_override=0.08, terminal_growth_rate=0.03))
        high_wacc = run_dcf(aapl_snapshot, DCFAssumptions(wacc_override=0.12, terminal_growth_rate=0.03))
        assert high_wacc.intrinsic_value_per_share < low_wacc.intrinsic_value_per_share

    def test_higher_growth_rate_increases_intrinsic_value(self, aapl_snapshot):
        low_growth = run_dcf(
            aapl_snapshot, DCFAssumptions(growth_rate=0.04, wacc_override=0.09, terminal_growth_rate=0.03)
        )
        high_growth = run_dcf(
            aapl_snapshot, DCFAssumptions(growth_rate=0.12, wacc_override=0.09, terminal_growth_rate=0.03)
        )
        assert high_growth.intrinsic_value_per_share > low_growth.intrinsic_value_per_share

    def test_higher_terminal_growth_increases_value(self, aapl_snapshot):
        low_tg = run_dcf(aapl_snapshot, DCFAssumptions(wacc_override=0.10, terminal_growth_rate=0.02))
        high_tg = run_dcf(aapl_snapshot, DCFAssumptions(wacc_override=0.10, terminal_growth_rate=0.04))
        assert high_tg.intrinsic_value_per_share > low_tg.intrinsic_value_per_share

    def test_premium_discount_sign_overvalued(self):
        # current_price >> intrinsic value -> positive premium (overvalued)
        snapshot = FinancialSnapshot(
            ticker="OVER", free_cash_flow_ttm=1e9, net_debt=0.0,
            shares_outstanding=1e9, current_price=500.0, beta=1.0,
        )
        result = run_dcf(snapshot, DCFAssumptions(wacc_override=0.10, terminal_growth_rate=0.03))
        assert result.premium_discount_pct > 0

    def test_premium_discount_sign_undervalued(self):
        snapshot = FinancialSnapshot(
            ticker="UNDER", free_cash_flow_ttm=5e9, net_debt=0.0,
            shares_outstanding=1e9, current_price=10.0, beta=1.0,
        )
        result = run_dcf(snapshot, DCFAssumptions(wacc_override=0.09, terminal_growth_rate=0.03))
        assert result.premium_discount_pct < 0

    def test_wacc_override_skips_computed_wacc(self, aapl_snapshot, base_assumptions):
        overridden = DCFAssumptions(
            growth_rate=base_assumptions.growth_rate,
            terminal_growth_rate=base_assumptions.terminal_growth_rate,
            projection_years=base_assumptions.projection_years,
            wacc_override=0.111,
        )
        result = run_dcf(aapl_snapshot, overridden)
        assert math.isclose(result.wacc, 0.111)

    def test_raises_if_assumptions_wacc_not_greater_than_terminal_growth(self):
        with pytest.raises(ValueError, match="must exceed terminal growth"):
            DCFAssumptions(wacc_override=0.03, terminal_growth_rate=0.03)

    def test_negative_net_debt_increases_equity_value_above_ev(self, base_assumptions):
        # Net cash position: equity value should exceed enterprise value
        snapshot = FinancialSnapshot(
            ticker="CASH", free_cash_flow_ttm=10e9, net_debt=-20e9,
            shares_outstanding=1e9, current_price=50.0, beta=1.0,
        )
        result = run_dcf(snapshot, base_assumptions)
        assert result.equity_value > result.enterprise_value

    def test_projected_fcf_length_matches_projection_years(self, aapl_snapshot):
        assumptions = DCFAssumptions(growth_rate=0.07, terminal_growth_rate=0.03, projection_years=8)
        result = run_dcf(aapl_snapshot, assumptions)
        assert len(result.projected_fcf) == 8
        assert len(result.pv_projected_fcf) == 8


# ── Input validation ──────────────────────────────────────────────────────

class TestValidation:
    def test_financial_snapshot_rejects_zero_shares(self):
        with pytest.raises(ValueError, match="shares_outstanding"):
            FinancialSnapshot(
                ticker="BAD", free_cash_flow_ttm=1e9, net_debt=0.0,
                shares_outstanding=0.0, current_price=10.0, beta=1.0,
            )

    def test_financial_snapshot_rejects_negative_price(self):
        with pytest.raises(ValueError, match="current_price"):
            FinancialSnapshot(
                ticker="BAD", free_cash_flow_ttm=1e9, net_debt=0.0,
                shares_outstanding=1e8, current_price=-5.0, beta=1.0,
            )

    def test_assumptions_rejects_zero_projection_years(self):
        with pytest.raises(ValueError, match="projection_years"):
            DCFAssumptions(projection_years=0)

    def test_assumptions_rejects_excessive_projection_years(self):
        with pytest.raises(ValueError, match="projection_years"):
            DCFAssumptions(projection_years=20)

    @pytest.mark.parametrize("years", [1, 3, 5, 10, 15])
    def test_assumptions_accepts_valid_projection_years(self, years):
        assumptions = DCFAssumptions(projection_years=years)
        assert assumptions.projection_years == years
