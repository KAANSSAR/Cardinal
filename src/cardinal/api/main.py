"""Cardinal FastAPI application."""
from __future__ import annotations

import httpx
import yfinance as yf

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from cardinal.api.models import (
    BacktestResponse, BalanceSheetResponse, CompsResponse, CurvePoint,
    DCFAssumptionsRequest, DCFResponse, IncomeStatementResponse,
    PeerMetricsOut, PriceHistoryResponse, PricePoint,
    QuantResponse, SearchResponse, SearchResult,
)
from cardinal.config import settings
from cardinal.core.backtest import run_mean_reversion_backtest, run_momentum_backtest
from cardinal.core.comps import PeerMetrics, compute_comps
from cardinal.core.dcf import DCFAssumptions, run_dcf
from cardinal.core.quant import benchmark_for_ticker, compute_quant_snapshot
from cardinal.data.fmp_client import (
    FMPNotConfiguredError, FMPRequestError,
    TickerNotFoundError as FMPTickerNotFoundError,
    get_balance_sheet_statement, get_income_statement,
    get_profile, get_stock_peers,
)
from cardinal.data.market_data import (
    InsufficientDataError, TickerNotFoundError,
    fetch_company_profile, fetch_financial_snapshot, fetch_price_history,
)

app = FastAPI(
    title="Cardinal API",
    description="Multi-lens equity analysis terminal.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search_tickers(q: str = Query(..., min_length=1)) -> SearchResponse:
    try:
        response = httpx.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": False},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5.0,
        )
        data = response.json()
        quotes = data.get("quotes", [])
        results = [
            SearchResult(
                symbol=quote["symbol"],
                name=quote.get("longname") or quote.get("shortname") or quote["symbol"],
                exchange=quote.get("exchange"),
                type=quote.get("quoteType"),
            )
            for quote in quotes
            if quote.get("symbol") and quote.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")
        ]
        return SearchResponse(query=q, results=results[:8])
    except Exception:
        return SearchResponse(query=q, results=[])


@app.get("/ticker/{symbol}/dcf", response_model=DCFResponse)
def get_dcf(
    symbol: str,
    growth_rate: float = 0.08,
    terminal_growth_rate: float = 0.035,
    projection_years: int = 5,
    wacc_override: float | None = None,
) -> DCFResponse:
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
        ticker=snapshot.ticker, company_name=profile.name,
        wacc=result.wacc, cost_of_equity=result.cost_of_equity,
        projected_fcf=result.projected_fcf, pv_projected_fcf=result.pv_projected_fcf,
        pv_terminal_value=result.pv_terminal_value,
        terminal_value_pct_of_ev=result.terminal_value_pct_of_ev,
        enterprise_value=result.enterprise_value, equity_value=result.equity_value,
        intrinsic_value_per_share=result.intrinsic_value_per_share,
        current_price=result.current_price, premium_discount_pct=result.premium_discount_pct,
    )


@app.get("/ticker/{symbol}/price-history", response_model=PriceHistoryResponse)
def get_price_history(symbol: str, period: str = "5y", interval: str = "1d") -> PriceHistoryResponse:
    try:
        history = fetch_price_history(symbol, period=period, interval=interval)
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    points = [
        PricePoint(
            date=str(index.date()), open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]), volume=int(row["Volume"]),
        )
        for index, row in history.iterrows()
    ]
    return PriceHistoryResponse(ticker=symbol.upper(), period=period, interval=interval, points=points)


@app.get("/ticker/{symbol}/income-statement", response_model=IncomeStatementResponse)
def get_income_statement_endpoint(symbol: str, limit: int = 3) -> IncomeStatementResponse:
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
    try:
        statements = get_balance_sheet_statement(symbol, limit=limit)
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except FMPTickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FMPRequestError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return BalanceSheetResponse(ticker=symbol.upper(), statements=statements)


def _build_peer_metrics_yf(ticker: str) -> PeerMetrics | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or (not info.get("regularMarketPrice") and not info.get("currentPrice")):
            return None
        market_cap = info.get("marketCap")
        name = info.get("longName") or info.get("shortName") or ticker
        revenue = info.get("totalRevenue")
        net_income = info.get("netIncomeToCommon")
        ebitda = info.get("ebitda")
        total_debt = info.get("totalDebt") or 0
        cash = info.get("totalCash") or 0
        ev_raw = (market_cap or 0) + total_debt - cash
        ev = ev_raw if ev_raw > 0 else None
        pe = info.get("trailingPE")
        ps = info.get("priceToSalesTrailing12Months")
        ev_ebitda = info.get("enterpriseToEbitda")
        ev_revenue = info.get("enterpriseToRevenue")
        if pe is None and market_cap and net_income and net_income > 0:
            pe = market_cap / net_income
        if ps is None and market_cap and revenue and revenue > 0:
            ps = market_cap / revenue
        if ev_ebitda is None and ev and ebitda and ebitda > 0:
            ev_ebitda = ev / ebitda
        if ev_revenue is None and ev and revenue and revenue > 0:
            ev_revenue = ev / revenue
        return PeerMetrics(
            ticker=ticker.upper(), name=name, market_cap=market_cap, enterprise_value=ev,
            ev_ebitda=ev_ebitda, pe_ratio=pe, ev_revenue=ev_revenue, ps_ratio=ps,
            revenue_ttm=revenue, ebitda_ttm=ebitda,
        )
    except Exception:
        return None


@app.get("/ticker/{symbol}/comps", response_model=CompsResponse)
def get_comps(symbol: str) -> CompsResponse:
    def _require_fmp() -> None:
        if not settings.fmp_configured:
            raise FMPNotConfiguredError("FMP_API_KEY is not set.")

    try:
        _require_fmp()
        peer_tickers = get_stock_peers(symbol)[:5]
        target_metrics = _build_peer_metrics_yf(symbol)
        if target_metrics is None:
            raise FMPRequestError(f"Could not fetch metrics for '{symbol}'")
        peers_built = [pm for t in peer_tickers if (pm := _build_peer_metrics_yf(t)) is not None]
        result = compute_comps(symbol.upper(), target_metrics, peers_built)
        peers_out = [
            PeerMetricsOut(
                ticker=p.ticker, name=p.name, market_cap=p.market_cap,
                enterprise_value=p.enterprise_value, ev_ebitda=p.ev_ebitda,
                pe_ratio=p.pe_ratio, ev_revenue=p.ev_revenue, ps_ratio=p.ps_ratio,
            )
            for p in result.peers
        ]
        return CompsResponse(
            ticker=symbol.upper(), peers=peers_out,
            median_ev_ebitda=result.median_ev_ebitda, median_pe=result.median_pe,
            median_ev_revenue=result.median_ev_revenue, median_ps=result.median_ps,
            implied_ev_from_ebitda=result.implied_ev_from_ebitda,
            implied_ev_from_revenue=result.implied_ev_from_revenue,
        )
    except FMPNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except (FMPRequestError, FMPTickerNotFoundError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/ticker/{symbol}/quant", response_model=QuantResponse)
def get_quant(symbol: str) -> QuantResponse:
    """
    Quantitative analytics overlay.
    Fetches 5y price history for the ticker and its benchmark,
    then computes momentum, Sharpe, beta, volatility surface, RSI, and Bollinger bands.
    """
    try:
        history = fetch_price_history(symbol, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{symbol}'")

    prices = history["Close"].dropna()
    benchmark_sym = benchmark_for_ticker(symbol)

    # Fetch benchmark — don't fail the whole request if it's unavailable
    bench_prices = None
    try:
        bench_hist = fetch_price_history(benchmark_sym, period="5y", interval="1d")
        if not bench_hist.empty:
            bench_prices = bench_hist["Close"].dropna()
    except Exception:
        pass

    try:
        snap = compute_quant_snapshot(symbol.upper(), prices, bench_prices)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quant computation failed: {e}") from e

    return QuantResponse(
        ticker=snap.ticker,
        current_price=snap.current_price,
        benchmark=benchmark_sym,
        momentum_20d=snap.momentum_20d,
        momentum_60d=snap.momentum_60d,
        momentum_252d=snap.momentum_252d,
        sharpe_60d=snap.sharpe_60d,
        sharpe_252d=snap.sharpe_252d,
        beta=snap.beta,
        vol_10d=snap.vol_10d,
        vol_30d=snap.vol_30d,
        vol_60d=snap.vol_60d,
        vol_252d=snap.vol_252d,
        rsi=snap.rsi,
        bb_upper=snap.bb_upper,
        bb_middle=snap.bb_middle,
        bb_lower=snap.bb_lower,
        bb_pct_b=snap.bb_pct_b,
    )


@app.get("/ticker/{symbol}/backtest", response_model=BacktestResponse)
def get_backtest(
    symbol: str,
    strategy: str = "momentum",
    fast_window: int = 50,
    slow_window: int = 200,
    lookback: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.0,
    commission: float = 0.001,
) -> BacktestResponse:
    """
    Algo backtest endpoint.
    strategy: 'momentum' (Golden/Death Cross) or 'mean_reversion' (z-score)
    """
    try:
        history = fetch_price_history(symbol, period="5y", interval="1d")
    except TickerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if history.empty:
        raise HTTPException(status_code=404, detail=f"No price history for '{symbol}'")

    prices = history["Close"].dropna()

    try:
        if strategy == "momentum":
            result = run_momentum_backtest(
                symbol.upper(), prices,
                fast_window=fast_window, slow_window=slow_window, commission=commission,
            )
        elif strategy == "mean_reversion":
            result = run_mean_reversion_backtest(
                symbol.upper(), prices,
                lookback=lookback, entry_z=entry_z, exit_z=exit_z, commission=commission,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown strategy '{strategy}'. Use 'momentum' or 'mean_reversion'.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return BacktestResponse(
        ticker=result.ticker,
        strategy=result.strategy,
        params=result.params,
        total_return=result.total_return,
        buy_hold_return=result.buy_hold_return,
        sharpe=result.sharpe,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        num_trades=result.num_trades,
        avg_win=result.avg_win,
        avg_loss=result.avg_loss,
        pnl_curve=[CurvePoint(date=p["date"], value=p["value"]) for p in result.pnl_curve],
        buy_hold_curve=[CurvePoint(date=p["date"], value=p["value"]) for p in result.buy_hold_curve],
    )