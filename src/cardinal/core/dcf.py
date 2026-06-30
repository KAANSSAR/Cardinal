"""
Discounted Cash Flow valuation engine.

Pure computation layer — takes a FinancialSnapshot and DCFAssumptions,
returns a DCFResult. No data fetching, no I/O. This separation mirrors
the options pricing engine's core/ modules: deterministic, unit-testable,
swappable data source.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialSnapshot:
    """Raw financial inputs for a single company, as of a point in time."""

    ticker: str
    free_cash_flow_ttm: float          # trailing twelve months FCF
    net_debt: float                    # total debt - cash & equivalents
    shares_outstanding: float
    current_price: float
    beta: float
    risk_free_rate: float = 0.042      # 10Y Treasury, default snapshot
    market_risk_premium: float = 0.055 # historical US equity risk premium
    cost_of_debt: float = 0.05
    tax_rate: float = 0.21
    market_cap: float | None = None    # used for E/V weight in WACC; falls back to price*shares
    total_debt: float | None = None    # used for D/V weight in WACC; falls back to net_debt

    def __post_init__(self) -> None:
        if self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be positive")
        if self.current_price < 0:
            raise ValueError("current_price cannot be negative")


@dataclass(frozen=True)
class DCFAssumptions:
    """User-adjustable valuation assumptions — these are the 'sliders'."""

    growth_rate: float = 0.08          # annual FCF growth, projection period
    terminal_growth_rate: float = 0.035
    projection_years: int = 5
    wacc_override: float | None = None  # if set, skips computed WACC

    def __post_init__(self) -> None:
        if self.projection_years < 1 or self.projection_years > 15:
            raise ValueError("projection_years must be between 1 and 15")
        if self.wacc_override is not None and self.wacc_override <= self.terminal_growth_rate:
            raise ValueError("WACC must exceed terminal growth rate (Gordon Growth requires wacc > g)")


@dataclass(frozen=True)
class DCFResult:
    wacc: float
    cost_of_equity: float
    projected_fcf: list[float]
    pv_projected_fcf: list[float]
    pv_terminal_value: float
    terminal_value_pct_of_ev: float
    enterprise_value: float
    equity_value: float
    intrinsic_value_per_share: float
    current_price: float
    premium_discount_pct: float  # (current - intrinsic) / intrinsic, positive = overvalued


def compute_cost_of_equity(beta: float, risk_free_rate: float, market_risk_premium: float) -> float:
    """CAPM: r_e = r_f + beta * (market risk premium)."""
    return risk_free_rate + beta * market_risk_premium


def compute_wacc(snapshot: FinancialSnapshot) -> float:
    """
    WACC = (E/V) * cost_of_equity + (D/V) * cost_of_debt * (1 - tax_rate)

    Falls back to price*shares for market cap and net_debt for total_debt
    if not explicitly provided — reasonable defaults for a quick valuation.
    """
    cost_of_equity = compute_cost_of_equity(
        snapshot.beta, snapshot.risk_free_rate, snapshot.market_risk_premium
    )

    market_cap = snapshot.market_cap or (snapshot.current_price * snapshot.shares_outstanding)
    total_debt = snapshot.total_debt if snapshot.total_debt is not None else max(snapshot.net_debt, 0.0)

    total_capital = market_cap + total_debt
    if total_capital <= 0:
        raise ValueError("Total capital (equity + debt) must be positive to compute WACC")

    equity_weight = market_cap / total_capital
    debt_weight = total_debt / total_capital

    after_tax_cost_of_debt = snapshot.cost_of_debt * (1 - snapshot.tax_rate)

    return equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt


def project_free_cash_flows(fcf_base: float, growth_rate: float, years: int) -> list[float]:
    """Project FCF forward using a constant annual growth rate."""
    return [fcf_base * (1 + growth_rate) ** year for year in range(1, years + 1)]


def discount_to_present_value(cash_flows: list[float], discount_rate: float) -> list[float]:
    """PV(CF_t) = CF_t / (1 + r)^t for each cash flow in the list."""
    return [cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(cash_flows)]


def terminal_value_gordon_growth(final_year_fcf: float, wacc: float, terminal_growth_rate: float) -> float:
    """
    TV = FCF_n * (1 + g) / (WACC - g), the standard Gordon Growth perpetuity.
    Caller is responsible for ensuring wacc > terminal_growth_rate.
    """
    if wacc <= terminal_growth_rate:
        raise ValueError("WACC must exceed terminal growth rate")
    return final_year_fcf * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)


def run_dcf(snapshot: FinancialSnapshot, assumptions: DCFAssumptions) -> DCFResult:
    """
    Full DCF pipeline: project FCF, discount to PV, add terminal value,
    derive enterprise value, equity value, and intrinsic value per share.
    """
    wacc = assumptions.wacc_override if assumptions.wacc_override is not None else compute_wacc(snapshot)
    cost_of_equity = compute_cost_of_equity(
        snapshot.beta, snapshot.risk_free_rate, snapshot.market_risk_premium
    )

    if wacc <= assumptions.terminal_growth_rate:
        raise ValueError(
            f"WACC ({wacc:.4f}) must exceed terminal growth rate "
            f"({assumptions.terminal_growth_rate:.4f}) for Gordon Growth to converge"
        )

    projected_fcf = project_free_cash_flows(
        snapshot.free_cash_flow_ttm, assumptions.growth_rate, assumptions.projection_years
    )
    pv_projected_fcf = discount_to_present_value(projected_fcf, wacc)

    terminal_value = terminal_value_gordon_growth(
        projected_fcf[-1], wacc, assumptions.terminal_growth_rate
    )
    pv_terminal_value = terminal_value / (1 + wacc) ** assumptions.projection_years

    enterprise_value = sum(pv_projected_fcf) + pv_terminal_value
    terminal_value_pct_of_ev = pv_terminal_value / enterprise_value if enterprise_value > 0 else 0.0

    equity_value = enterprise_value - snapshot.net_debt
    intrinsic_value_per_share = equity_value / snapshot.shares_outstanding

    premium_discount_pct = (
        (snapshot.current_price - intrinsic_value_per_share) / intrinsic_value_per_share
        if intrinsic_value_per_share != 0
        else 0.0
    )

    return DCFResult(
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        projected_fcf=projected_fcf,
        pv_projected_fcf=pv_projected_fcf,
        pv_terminal_value=pv_terminal_value,
        terminal_value_pct_of_ev=terminal_value_pct_of_ev,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        intrinsic_value_per_share=intrinsic_value_per_share,
        current_price=snapshot.current_price,
        premium_discount_pct=premium_discount_pct,
    )
