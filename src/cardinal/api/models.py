from __future__ import annotations
from pydantic import BaseModel, Field


class DCFAssumptionsRequest(BaseModel):
    growth_rate: float = Field(default=0.08, ge=-0.5, le=1.0)
    terminal_growth_rate: float = Field(default=0.035, ge=0.0, le=0.10)
    projection_years: int = Field(default=5, ge=1, le=15)
    wacc_override: float | None = Field(default=None, ge=0.0, le=0.5)


class DCFResponse(BaseModel):
    ticker: str
    company_name: str
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
    premium_discount_pct: float


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    points: list[PricePoint]


class IncomeStatementResponse(BaseModel):
    ticker: str
    statements: list[dict]


class BalanceSheetResponse(BaseModel):
    ticker: str
    statements: list[dict]


class PeerMetricsOut(BaseModel):
    ticker: str
    name: str
    market_cap: float | None
    enterprise_value: float | None
    ev_ebitda: float | None
    pe_ratio: float | None
    ev_revenue: float | None
    ps_ratio: float | None


class CompsResponse(BaseModel):
    ticker: str
    peers: list[PeerMetricsOut]
    median_ev_ebitda: float | None
    median_pe: float | None
    median_ev_revenue: float | None
    median_ps: float | None
    implied_ev_from_ebitda: float | None
    implied_ev_from_revenue: float | None


class SearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str | None
    type: str | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class QuantResponse(BaseModel):
    ticker: str
    current_price: float
    benchmark: str

    # Momentum
    momentum_20d: float | None
    momentum_60d: float | None
    momentum_252d: float | None

    # Sharpe
    sharpe_60d: float | None
    sharpe_252d: float | None

    # Beta
    beta: float | None

    # Volatility surface
    vol_10d: float | None
    vol_30d: float | None
    vol_60d: float | None
    vol_252d: float | None

    # RSI & Bollinger
    rsi: float | None
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    bb_pct_b: float | None


class CurvePoint(BaseModel):
    date: str
    value: float


class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    params: dict

    total_return: float
    buy_hold_return: float
    sharpe: float | None
    max_drawdown: float
    win_rate: float | None
    num_trades: int
    avg_win: float | None
    avg_loss: float | None

    pnl_curve: list[CurvePoint]
    buy_hold_curve: list[CurvePoint]


class ErrorResponse(BaseModel):
    detail: str