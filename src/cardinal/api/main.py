"""Cardinal FastAPI application — entrypoint and route definitions."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from cardinal.api.models import (
    BalanceSheetResponse,
    DCFAssumptionsRequest,
    DCFResponse,
    IncomeStatementResponse,
    PriceHistoryResponse,
    PricePoint,
)
from cardinal.core.dcf import DCFAssumptions, run_dcf
from cardinal.data.fmp_client import FMPNotConfiguredError
from cardinal.data.fmp_client import FMPRequestError as FMPRequestError
from cardinal.data.fmp_client import TickerNotFoundError as FMPTickerNotFoundError
from cardinal.data.fmp_client import get_balance_sheet_statement, get_income_statement
from cardinal.data.market_data import (
    InsufficientDataError,
    TickerNotFoundError,
    fetch_company_profile,
    fetch_financial_snapshot,
    fetch_price_history,
)

app = FastAPI(
    title="Cardinal API",
    description="Multi-lens equity analysis terminal — fundamental, quant, and algo backtesting.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite / CRA dev servers
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ticker/{symbol}/dcf", response_model=DCFResponse)
def get_dcf(
    symbol: str,
    growth_rate: float = 0.08,
    terminal_growth_rate: float = 0.035,
    projection_years: int = 5,
    wacc_override: float | None = None,
) -> DCFResponse:
    """
    Run a DCF valuation for the given ticker. Query params map to the
    frontend's editable assumption sliders — every change triggers a
    fresh request here, which is cheap since the DCF itself is pure
    arithmetic (the expensive part is the upstream yfinance fetch,
    which gets cached separately).
    """
    try:
        snapshot = fetch_financial_snapshot(symbol)
        profile = fetch_company_profile(symbol)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        request = DCFAssumptionsRequest(
            growth_rate=growth_rate,
            terminal_growth_rate=terminal_growth_rate,
            projection_years=projection_years,
            wacc_override=wacc_override,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        assumptions = DCFAssumptions(
            growth_rate=request.growth_rate,
            terminal_growth_rate=request.terminal_growth_rate,
            projection_years=request.projection_years,
            wacc_override=request.wacc_override,
        )
        result = run_dcf(snapshot, assumptions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return DCFResponse(
        ticker=snapshot.ticker,
        company_name=profile.name,
        wacc=result.wacc,
        cost_of_equity=result.cost_of_equity,
        projected_fcf=result.projected_fcf,
        pv_projected_fcf=result.pv_projected_fcf,
        pv_terminal_value=result.pv_terminal_value,
        terminal_value_pct_of_ev=result.terminal_value_pct_of_ev,
        enterprise_value=result.enterprise_value,
        equity_value=result.equity_value,
        intrinsic_value_per_share=result.intrinsic_value_per_share,
        current_price=result.current_price,
        premium_discount_pct=result.premium_discount_pct,
    )


@app.get("/ticker/{symbol}/price-history", response_model=PriceHistoryResponse)
def get_price_history(
    symbol: str,
    period: str = "5y",
    interval: str = "1d",
) -> PriceHistoryResponse:
    """
    OHLCV price history via yfinance. Feeds the quant overlay and
    backtest lenses (not yet built) as well as the price chart on the
    fundamental view. Kept on yfinance rather than FMP since yfinance's
    free coverage of EU/India price history is broader.
    """
    try:
        history = fetch_price_history(symbol, period=period, interval=interval)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    points = [
        PricePoint(
            date=str(index.date()),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
        )
        for index, row in history.iterrows()
    ]

    return PriceHistoryResponse(ticker=symbol.upper(), period=period, interval=interval, points=points)


@app.get("/ticker/{symbol}/income-statement", response_model=IncomeStatementResponse)
def get_income_statement_endpoint(symbol: str, limit: int = 3) -> IncomeStatementResponse:
    """Annual income statements via FMP. Powers the financial statement viewer."""
    try:
        statements = get_income_statement(symbol, limit=limit)
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except FMPTickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FMPRequestError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return IncomeStatementResponse(ticker=symbol.upper(), statements=statements)


@app.get("/ticker/{symbol}/balance-sheet", response_model=BalanceSheetResponse)
def get_balance_sheet_endpoint(symbol: str, limit: int = 3) -> BalanceSheetResponse:
    """Annual balance sheets via FMP. Powers the financial statement viewer."""
    try:
        statements = get_balance_sheet_statement(symbol, limit=limit)
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except FMPTickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FMPRequestError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return BalanceSheetResponse(ticker=symbol.upper(), statements=statements)
