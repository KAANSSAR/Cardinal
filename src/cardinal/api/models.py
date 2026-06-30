"""Pydantic request/response models — the contract between backend and frontend."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DCFAssumptionsRequest(BaseModel):
    """Maps directly to the frontend's WACC / growth / years sliders."""

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


class ErrorResponse(BaseModel):
    detail: str
